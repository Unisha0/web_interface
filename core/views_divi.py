from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta
from decimal import Decimal
import json

from .models import Lead
from .forms import (
    SalesLeadForm,
    IntakeDetailForm,
    PricingReviewForm,
    ProductionStatusForm,
    InvoiceApprovalForm,
    DeliveryFeedbackForm,
    SupportTicketForm,
)
from .pricing import PRICING_CONFIG, PRIORITY_RULES, calculate_project_price, get_rough_price_estimate


# ============================================================================
# STEP 1: SALES / LEAD CAPTURE
# ============================================================================

def sales_lead_view(request):
    """
    Step 1: Collect initial lead info (name, email, phone, service type, timeline)
    Rules:
    - Structured conversation only
    - Mandatory info before progressing
    - Phone is seriousness gate
    - Optional human handoff
    """
    if request.method == 'POST':
        form = SalesLeadForm(request.POST)
        if form.is_valid():
            # Prepare lead data
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            service_type = form.cleaned_data['service_type']
            timeline = form.cleaned_data['timeline']
            message = form.cleaned_data.get('message', '')
            want_human = form.cleaned_data.get('want_human', False)
            
            # Create lead record (seriousness determined by phone capture)
            lead = Lead.objects.create(
                name=name,
                email=email,
                phone=phone,
                source='direct',
                source_campaign='sales_form',
                project_type=service_type,
                timeline=timeline,
                first_message=message,
                first_message_summary=message[:180] if message else '',
                is_serious=True,  # Phone capture = serious intent
                stage='new',
                current_workflow_step='sales',
                human_requested=want_human,
            )
            
            # Rule: If human requested → route to human
            if want_human:
                lead.stage = 'human_handoff'
                lead.save()
                messages.success(request, f'Thank you {name}! A human representative will contact you shortly at {phone}.')
                return redirect('sales_success')
            
            # Rule: Provide rough pricing for serious clients
            rough_price = get_rough_price_estimate(service_type, service_type)
            
            # Redirect to intake
            request.session['lead_id'] = lead.id
            request.session['rough_price'] = str(rough_price)
            
            return redirect('intake_requirements')
    else:
        form = SalesLeadForm()
    
    return render(request, 'sales_lead.html', {'form': form, 'step': 1})


# ============================================================================
# STEP 2: INTAKE / REQUIREMENTS GATHERING
# ============================================================================

def intake_requirements_view(request):
    """
    Step 2: Collect detailed project requirements
    Rules:
    - All client requirements must be captured
    - Structured intake form mandatory
    - AI verifies completeness
    """
    lead_id = request.session.get('lead_id')
    if not lead_id:
        messages.error(request, 'Please start from the beginning.')
        return redirect('sales_lead')
    
    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == 'POST':
        form = IntakeDetailForm(request.POST)
        if form.is_valid():
            # Update lead with intake data
            lead.pages_count = form.cleaned_data.get('pages_count')
            lead.content_delivery = form.cleaned_data.get('content_delivery')
            lead.business_name = form.cleaned_data.get('business_name', '')
            lead.client_need_details = form.cleaned_data.get('project_description', '')
            lead.current_workflow_step = 'intake'
            lead.stage = 'qualified'
            lead.save()
            
            # Store intake data in session for next step
            request.session['project_description'] = form.cleaned_data.get('project_description')
            
            return redirect('pricing_quotation')
    else:
        form = IntakeDetailForm()
    
    rough_price = request.session.get('rough_price', 'Pending full intake')
    return render(request, 'intake_requirements.html', {
        'form': form,
        'lead': lead,
        'rough_price': rough_price,
        'step': 2,
    })


# ============================================================================
# STEP 3: PRICING / QUOTATION
# ============================================================================

def pricing_quotation_view(request):
    """
    Step 3: Generate automatic quote based on intake data
    Rules:
    - Exact pricing calculated AFTER intact
    - Priority projects may add surcharge
    - AI generates quote; human approval optional
    """
    lead_id = request.session.get('lead_id')
    if not lead_id:
        return redirect('sales_lead')
    
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Calculate base price based on service type and selections
    quote_data = calculate_quote(lead)
    
    if request.method == 'POST':
        form = PricingReviewForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('approve_quote'):
                # Generate invoice
                lead.quote_price = Decimal(str(quote_data['total']))
                lead.quote_breakdown = quote_data
                lead.quote_status = 'approved'
                lead.quote_date = timezone.now()
                lead.current_workflow_step = 'pricing'
                lead.save()
                
                request.session['quote_price'] = float(quote_data['total'])
                return redirect('invoice_generation')
            else:
                messages.info(request, 'Please review the quote and approve to proceed.')
    else:
        form = PricingReviewForm()
    
    return render(request, 'pricing_quotation.html', {
        'form': form,
        'lead': lead,
        'quote': quote_data,
        'step': 3,
    })


def calculate_quote(lead):
    """
    Intelligent quote calculation based on service type and intake data
    """
    base_price = 0
    addons_cost = 0
    addons_list = []
    
    # Service-specific base pricing
    if lead.project_type == 'cms':
        pages = lead.pages_count or 5
        if pages == 1:
            base_price = 149
        else:
            base_price = 299
        
    elif lead.project_type == 'ecommerce':
        base_price = 450  # WooCommerce basic
        
    elif lead.project_type == 'ai':
        base_price = 125  # AI Chat setup
        
    elif lead.project_type == 'flutter':
        base_price = 400  # Corporate app
        
    elif lead.project_type == 'custom':
        base_price = 750  # 50 hours at $15/hour
        
    elif lead.project_type == 'video':
        base_price = 75  # 30 sec
        
    elif lead.project_type == 'design':
        base_price = 60  # Basic logo
        
    elif lead.project_type == 'social':
        base_price = 75  # Campaign setup
        
    elif lead.project_type == 'hosting':
        base_price = 5  # Basic shared hosting
    
    # Apply priority surcharge
    priority = lead.timeline or 'normal'
    multiplier = PRIORITY_RULES.get(priority, {}).get('multiplier', 1.0)
    base_price = round(base_price * multiplier, 2)
    
    # Build quote breakdown
    total = base_price
    
    breakdown = {
        'service': lead.get_project_type_display(),
        'base_price': base_price,
        'addons': addons_list,
        'addons_cost': addons_cost,
        'priority': priority,
        'priority_multiplier': multiplier,
        'total': total,
        'created_at': timezone.now().isoformat(),
    }
    
    return breakdown


# ============================================================================
# STEP 4: PRODUCTION / PROJECT EXECUTION
# ============================================================================

def production_tracking_view(request):
    """
    Step 4: Track project progress through milestones
    """
    lead_id = request.session.get('lead_id')
    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == 'POST':
        form = ProductionStatusForm(request.POST)
        if form.is_valid():
            lead.current_milestone = form.cleaned_data['current_milestone']
            lead.production_status = 'in_progress'
            lead.current_workflow_step = 'production'
            lead.project_start_date = timezone.now().date()
            lead.expected_completion_date = timezone.now().date() + timedelta(days=10)
            lead.save()
            
            messages.success(request, 'Project status updated!')
            return redirect('production_tracking')
    else:
        form = ProductionStatusForm()
        if lead.current_milestone:
            form = ProductionStatusForm(initial={'current_milestone': lead.current_milestone})
    
    return render(request, 'production_tracking.html', {
        'form': form,
        'lead': lead,
        'step': 4,
    })


# ============================================================================
# STEP 5: INVOICE GENERATION & PAYMENT
# ============================================================================

def invoice_generation_view(request):
    """
    Step 5: Generate and track invoice
    """
    lead_id = request.session.get('lead_id')
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Generate invoice number if not exists
    if not lead.invoice_id:
        lead.invoice_id = f"INV-{lead.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        lead.invoice_sent_date = timezone.now()
        lead.current_workflow_step = 'invoice'
        lead.save()
    
    if request.method == 'POST':
        form = InvoiceApprovalForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('payment_received'):
                lead.payment_status = 'paid'
                lead.payment_date = timezone.now()
                lead.stage = 'won'
                lead.save()
                
                messages.success(request, 'Payment recorded! Project will now be deployed.')
                return redirect('delivery_feedback')
    else:
        form = InvoiceApprovalForm()
    
    return render(request, 'invoice_generation.html', {
        'form': form,
        'lead': lead,
        'invoice_id': lead.invoice_id,
        'amount_due': lead.quote_price,
        'step': 5,
    })


# ============================================================================
# STEP 6: POST-DELIVERY REVIEW & FEEDBACK
# ============================================================================

def delivery_feedback_view(request):
    """
    Step 6: Collect client feedback and rate service
    """
    lead_id = request.session.get('lead_id')
    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == 'POST':
        form = DeliveryFeedbackForm(request.POST)
        if form.is_valid():
            lead.rating = Decimal(form.cleaned_data['rating'])
            lead.client_feedback = form.cleaned_data['feedback']
            lead.feedback_received_date = timezone.now()
            lead.delivered_date = timezone.now()
            lead.current_workflow_step = 'delivery'
            lead.save()
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect('support_tickets')
    else:
        form = DeliveryFeedbackForm()
    
    return render(request, 'delivery_feedback.html', {
        'form': form,
        'lead': lead,
        'step': 6,
    })


# ============================================================================
# STEP 7: SUPPORT & MAINTENANCE
# ============================================================================

def support_tickets_view(request):
    """
    Step 7: Log and track support issues
    """
    lead_id = request.session.get('lead_id')
    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            # Log support ticket
            ticket = {
                'id': len(lead.support_issues) + 1,
                'type': form.cleaned_data['issue_type'],
                'subject': form.cleaned_data['subject'],
                'description': form.cleaned_data['description'],
                'priority': form.cleaned_data['priority'],
                'status': 'open',
                'created_at': timezone.now().isoformat(),
            }
            
            support_issues = lead.support_issues or []
            support_issues.append(ticket)
            lead.support_issues = support_issues
            lead.support_active = True
            lead.current_workflow_step = 'support'
            lead.save()
            
            messages.success(request, f'Support ticket #{ticket["id"]} created!')
            return redirect('support_tickets')
    else:
        form = SupportTicketForm()
    
    return render(request, 'support_tickets.html', {
        'form': form,
        'lead': lead,
        'support_issues': lead.support_issues or [],
        'step': 7,
    })


# ============================================================================
# SUCCESS & HELPER VIEWS
# ============================================================================

def sales_success_view(request):
    """Confirmation page after lead capture"""
    return render(request, 'sales_success.html')


def workflow_dashboard_view(request):
    """View all leads and their workflow status"""
    leads = Lead.objects.all().order_by('-created_at')
    leads_won = leads.filter(stage='won').count()
    leads_active = leads.filter(production_status='in_progress').count()
    leads_support = leads.filter(support_active=True).count()
    return render(request, 'workflow_dashboard.html', {
        'leads': leads,
        'leads_won': leads_won,
        'leads_active': leads_active,
        'leads_support': leads_support,
    })
