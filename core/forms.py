from django import forms
from .models import Lead
from .pricing import PRICING_CONFIG


# ============================================================================
# DIVI HOSTING: 7-Step Workflow Forms
# ============================================================================


class SalesLeadForm(forms.Form):
    """
    Step 1: Sales/Lead Capture Form
    Collects: Name, Email, Phone, Service Type, Timeline, Priority
    """
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your full name',
            'autofocus': True,
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com',
        })
    )
    
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1 (555) 000-0000',
        })
    )
    
    SERVICE_CHOICES = [
        ('cms', '🌐 CMS Web Development (WordPress, Wix, Squarespace, Webflow)'),
        ('ecommerce', '🛒 Ecommerce (WooCommerce, Magento)'),
        ('ai', '🤖 AI Services (Chat, Booking, Business)'),
        ('flutter', '📱 Flutter Apps (Corporate, Booking)'),
        ('custom', '⚙️ Custom Development (CRM, ERP, NodeJS, Laravel)'),
        ('video', '🎬 Video Editing'),
        ('design', '🎨 Graphic Design (Logos, Social)'),
        ('social', '📢 Social Media Promotion'),
        ('hosting', '🖥️ Hosting Solutions'),
        ('support', '💬 Support Hours'),
    ]
    
    service_type = forms.ChoiceField(
        choices=SERVICE_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    
    TIMELINE_CHOICES = [
        ('normal', 'Normal (7-10 days)'),
        ('fast', 'Fast (3-5 days) - +20%'),
        ('urgent', 'Urgent (1-2 days) - +50%'),
    ]
    
    timeline = forms.ChoiceField(
        choices=TIMELINE_CHOICES,
        required=True,
        initial='normal',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    
    message = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Tell us about your project (optional)',
            'rows': 3,
        })
    )
    
    want_human = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I prefer to speak with a human representative',
    )


class IntakeDetailForm(forms.Form):
    """
    Step 2: Intake/Requirements Gathering
    """
    project_description = forms.CharField(
        max_length=1000,
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Describe your project in detail...',
            'rows': 4,
        })
    )
    
    CONTENT_DELIVERY_CHOICES = [
        ('client_provides', 'Client will provide content/images/assets'),
        ('we_create', 'We will create content (additional cost)'),
        ('mixed', 'Mixed approach'),
    ]
    
    content_delivery = forms.ChoiceField(
        choices=CONTENT_DELIVERY_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    
    pages_count = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Number of pages',
        })
    )
    
    business_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Business name',
        })
    )
    
    technical_requirements = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Any specific technical integrations or requirements?',
            'rows': 2,
        })
    )


class PricingReviewForm(forms.Form):
    """Step 3: Pricing/Quote Review"""
    approve_quote = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I approve this quotation and want to proceed',
    )
    
    notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Any questions about the quote?',
            'rows': 2,
        })
    )


class ProductionStatusForm(forms.Form):
    """Step 4: Production/Project Execution"""
    MILESTONE_CHOICES = [
        ('content_setup', 'Content Setup'),
        ('design', 'Design'),
        ('development', 'Development'),
        ('addons', 'Add-ons'),
        ('qa', 'Quality Assurance'),
        ('review', 'Review'),
        ('completed', 'Completed'),
    ]
    
    current_milestone = forms.ChoiceField(
        choices=MILESTONE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    
    progress_update = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Progress update...',
            'rows': 3,
        })
    )


class InvoiceApprovalForm(forms.Form):
    """Step 5: Invoice Review & Payment"""
    payment_received = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Mark payment as received',
    )


class DeliveryFeedbackForm(forms.Form):
    """Step 6: Post-Delivery Feedback"""
    RATING_CHOICES = [
        ('5', '⭐⭐⭐⭐⭐ Excellent'),
        ('4', '⭐⭐⭐⭐ Very Good'),
        ('3', '⭐⭐⭐ Good'),
        ('2', '⭐⭐ Fair'),
        ('1', '⭐ Needs Improvement'),
    ]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='How would you rate this project?',
    )
    
    feedback = forms.CharField(
        max_length=1000,
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Share your feedback...',
            'rows': 4,
        })
    )


class SupportTicketForm(forms.Form):
    """Step 7: Support & Maintenance"""
    ISSUE_CHOICES = [
        ('bug', 'Bug Report'),
        ('feature', 'Feature Request'),
        ('performance', 'Performance Issue'),
        ('security', 'Security'),
        ('general', 'General Support'),
    ]
    
    issue_type = forms.ChoiceField(
        choices=ISSUE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    
    subject = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Issue subject',
        })
    )
    
    description = forms.CharField(
        max_length=2000,
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Detailed description...',
            'rows': 4,
        })
    )
    
    priority = forms.ChoiceField(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
        ],
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )


# ============================================================================
# LEGACY FORMS (for backward compatibility with existing views)
# ============================================================================

class SalesForm(forms.Form):
    """Legacy form - kept for backward compatibility"""
    name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    PROJECT_CHOICES = [
        ('cms', 'CMS Website'),
        ('ecommerce', 'Ecommerce'),
        ('ai', 'AI Service'),
        ('custom', 'Custom Development'),
    ]
    
    project_type = forms.ChoiceField(choices=PROJECT_CHOICES, widget=forms.RadioSelect())
    
    TIMELINE_CHOICES = [
        ('normal', 'Normal'),
        ('fast', 'Fast'),
        ('urgent', 'Urgent'),
    ]
    
    timeline = forms.ChoiceField(choices=TIMELINE_CHOICES, widget=forms.RadioSelect())
    
    HUMAN_CHOICES = [
        ('ai', 'Continue with AI'),
        ('human', 'Talk to human'),
    ]
    
    contact_preference = forms.ChoiceField(choices=HUMAN_CHOICES, widget=forms.RadioSelect())


class IntakeForm(forms.Form):
    """Legacy form - kept for backward compatibility"""
    pages = forms.IntegerField(required=False, min_value=1, initial=5)
    
    ADDONS = [
        ('seo', 'SEO'),
        ('booking', 'Booking System'),
        ('security', 'Security'),
    ]
    
    addons = forms.MultipleChoiceField(choices=ADDONS, required=False, widget=forms.CheckboxSelectMultiple)
    
    content = forms.ChoiceField(choices=[('client', 'Client provides'), ('company', 'We create')])
    
    timeline_confirm = forms.ChoiceField(choices=[
        ('normal', 'Normal'),
        ('fast', 'Fast'),
        ('urgent', 'Urgent'),
    ])
