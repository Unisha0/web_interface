from django.db import models
import json


class Lead(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=120, blank=True, default='')
    email = models.EmailField()
    phone = models.CharField(max_length=30, default='')
    first_message = models.TextField(default='')
    first_message_summary = models.TextField(default='')
    business_name = models.CharField(max_length=120, blank=True, default='')
    current_presence_link = models.CharField(max_length=255, blank=True, default='')
    client_need = models.CharField(max_length=40, default='website_presence')
    client_need_details = models.TextField(blank=True, default='')
    expected_benefit = models.CharField(max_length=40, default='increase_sales')
    expected_benefit_details = models.TextField(blank=True, default='')
    willing_to_call = models.BooleanField(default=False)
    can_pay_deposit = models.BooleanField(default=False)
    assets_ready = models.BooleanField(default=False)
    logo_ready = models.BooleanField(default=False)
    content_ready = models.BooleanField(default=False)
    images_ready = models.BooleanField(default=False)

    SOURCE_CHOICES = [
        ('facebook', 'Facebook'),
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('google', 'Google Ads'),
        ('website', 'Website'),
        ('referral', 'Referral'),
        ('other', 'Other'),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='other')
    source_campaign = models.CharField(max_length=120, blank=True, default='')
    source_detected_by = models.CharField(max_length=20, default='auto')
    
    PROJECT_CHOICES = [
        ('cms', 'CMS Website'),
        ('ecommerce', 'Ecommerce'),
        ('ai', 'AI Service'),
        ('custom', 'Custom Development'),
    ]
    
    project_type = models.CharField(max_length=50, choices=PROJECT_CHOICES)

    GOAL_CHOICES = [
        ('website_presence', 'Website Presence'),
        ('online_sales', 'Online Sales'),
        ('automation', 'Automation'),
        ('branding', 'Branding'),
        ('social_only', 'Social Media Presence Only'),
    ]
    primary_goal = models.CharField(max_length=30, choices=GOAL_CHOICES, default='website_presence')

    BUDGET_CHOICES = [
        ('low', 'Below $300'),
        ('mid', '$300 to $1000'),
        ('high', 'Above $1000'),
        ('undecided', 'Undecided'),
    ]
    budget_range = models.CharField(max_length=20, choices=BUDGET_CHOICES, default='undecided')
    is_decision_maker = models.BooleanField(default=False)
    business_ready = models.BooleanField(default=False)
    
    TIMELINE_CHOICES = [
        ('normal', 'Normal'),
        ('fast', 'Fast'),
        ('urgent', 'Urgent'),
    ]
    
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES)
    
    contact_preference = models.CharField(max_length=20)

    STAGE_CHOICES = [
        ('new', 'New Lead'),
        ('qualified', 'Qualified'),
        ('unqualified', 'Unqualified'),
        ('proposal_sent', 'Proposal Sent'),
        ('human_handoff', 'Human Handoff'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default='new')
    lead_score = models.PositiveIntegerField(default=0)
    seriousness_level = models.CharField(max_length=10, default='cold')
    next_action = models.CharField(max_length=120, blank=True, default='')
    is_serious = models.BooleanField(default=False)
    needs_human = models.BooleanField(default=False)
    recommended_service = models.CharField(max_length=50, blank=True, default='')
    disqualification_reason = models.TextField(blank=True, default='')

    # Processor pipeline tracking
    processor_phase = models.CharField(max_length=30, default='LEAD_CAPTURE')
    readiness_percent = models.PositiveIntegerField(default=0)
    risk_flags = models.JSONField(default=list, blank=True)
    contact_block_complete = models.BooleanField(default=False)
    service_block_complete = models.BooleanField(default=False)
    delivery_block_complete = models.BooleanField(default=False)
    qualified_for_handoff = models.BooleanField(default=False)
    risk_check_required = models.BooleanField(default=False)
    service_plan = models.CharField(max_length=100, blank=True, default='')

    rough_price = models.CharField(max_length=100, blank=True, null=True)

    # Multi-service fields for Divi Hosting platform
    service_category = models.ForeignKey('ServiceCategory', on_delete=models.SET_NULL, blank=True, null=True)
    selected_package = models.ForeignKey('ServicePackage', on_delete=models.SET_NULL, blank=True, null=True)
    selected_addons = models.ManyToManyField('ServiceAddOn', blank=True)
    service_specific_data = models.JSONField(default=dict, blank=True)  # Store service-specific questions/answers
    
    # Workflow tracking fields (7-step process)
    current_workflow_step = models.CharField(max_length=50, default='sales', choices=[
        ('sales', 'Sales/Lead Capture'),
        ('intake', 'Intake/Requirements'),
        ('pricing', 'Pricing/Quote'),
        ('production', 'Production/Execution'),
        ('invoice', 'Invoice Generated'),
        ('delivery', 'Delivered/Review'),
        ('support', 'Support'),
    ])
    
    priority = models.CharField(max_length=20, default='normal', choices=[
        ('normal', 'Normal (7-10 days)'),
        ('fast', 'Fast (3-5 days)'),
        ('urgent', 'Urgent (1-2 days)'),
    ])
    
    human_requested = models.BooleanField(default=False)
    is_serious = models.BooleanField(default=False)  # Determined after phone capture
    
    # Intake data (Step 2)
    pages_count = models.PositiveIntegerField(blank=True, null=True)  # For website projects
    selected_features = models.JSONField(default=list, blank=True)  # Selected add-ons
    content_delivery = models.CharField(max_length=50, blank=True, choices=[
        ('client_provides', 'Client provides content/assets'),
        ('we_create', 'We create content'),
        ('mixed', 'Mixed approach'),
    ])
    
    # Pricing data (Step 3)
    quote_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    quote_breakdown = models.JSONField(default=dict, blank=True)  # Itemized pricing
    quote_date = models.DateTimeField(blank=True, null=True)
    quote_status = models.CharField(max_length=20, default='draft', choices=[
        ('draft', 'Draft'),
        ('sent', 'Sent to client'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ])
    
    # Production tracking (Step 4)
    project_start_date = models.DateField(blank=True, null=True)
    expected_completion_date = models.DateField(blank=True, null=True)
    current_milestone = models.CharField(max_length=100, blank=True, default='')  # Content setup, Design, Dev, etc.
    production_status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
    ])
    
    # Invoice tracking (Step 5)
    invoice_id = models.CharField(max_length=100, blank=True, default='')
    invoice_sent_date = models.DateTimeField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='unpaid', choices=[
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial Payment'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ])
    payment_date = models.DateTimeField(blank=True, null=True)
    
    # Delivery & Feedback (Step 6)
    delivered_date = models.DateTimeField(blank=True, null=True)
    client_feedback = models.TextField(blank=True, default='')
    rating = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)  # 1-5 stars
    feedback_received_date = models.DateTimeField(blank=True, null=True)
    
    # Support & Maintenance (Step 7)
    support_tier = models.CharField(max_length=20, blank=True, choices=[
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('advanced', 'Advanced'),
    ])
    support_active = models.BooleanField(default=False)
    support_issues = models.JSONField(default=list, blank=True)  # Logged tickets

    # End-of-chat customer satisfaction
    csat_helpful = models.BooleanField(blank=True, null=True)
    csat_comment = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} | {self.get_project_type_display()} | {self.get_stage_display()}"


class Intake(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    pages = models.IntegerField(default=1)
    addons = models.TextField(blank=True)  # store as comma-separated
    content = models.CharField(max_length=50)
    branding_ready = models.CharField(max_length=20, default='client')
    integrations = models.TextField(blank=True, default='')
    ecommerce_platform = models.CharField(max_length=20, blank=True, default='')
    ai_package = models.CharField(max_length=20, blank=True, default='')
    custom_package = models.CharField(max_length=20, blank=True, default='')
    timeline_confirm = models.CharField(max_length=20, default='normal')
    is_complete = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Intake #{self.id} for {self.lead.name}"


class Quote(models.Model):
    intake = models.ForeignKey(Intake, on_delete=models.CASCADE)
    total_price = models.FloatField()
    monthly_cost = models.FloatField(blank=True, null=True)
    breakdown = models.TextField()
    notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quote #{self.id} | ${self.total_price}"


class FollowUpTask(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    day_offset = models.PositiveSmallIntegerField(default=1)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=20, default='pending')
    message = models.TextField(blank=True, default='')
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FollowUp #{self.id} for {self.lead.name} (D+{self.day_offset})"


class Invoice(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    quote = models.OneToOneField(Quote, on_delete=models.SET_NULL, blank=True, null=True)
    invoice_number = models.CharField(max_length=40, unique=True)
    subtotal = models.FloatField(default=0)
    discount = models.FloatField(default=0)
    surcharge = models.FloatField(default=0)
    total_amount = models.FloatField(default=0)
    outstanding_balance = models.FloatField(default=0)
    payment_terms = models.CharField(max_length=120, default='Payment due in 7 days')
    due_date = models.DateField()
    status = models.CharField(max_length=20, default='sent')
    sent_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    last_reminder_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice_number} | {self.lead.name}"


class PaymentReminder(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    reminder_type = models.CharField(max_length=20, default='pre_due')
    sent_at = models.DateTimeField(auto_now_add=True)
    channel = models.CharField(max_length=20, default='email')
    note = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Reminder {self.reminder_type} for {self.invoice.invoice_number}"


class ProjectExecution(models.Model):
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE)
    invoice = models.OneToOneField(Invoice, on_delete=models.SET_NULL, blank=True, null=True)
    status = models.CharField(max_length=20, default='active')
    start_date = models.DateField(blank=True, null=True)
    expected_delivery = models.DateField(blank=True, null=True)
    is_priority = models.BooleanField(default=False)
    assigned_to = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Project for {self.lead.name}"


class ProjectMilestone(models.Model):
    project = models.ForeignKey(ProjectExecution, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    order = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, default='pending')
    eta = models.DateField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    client_update = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.project.lead.name}: {self.name}"


class CommunicationLog(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    project = models.ForeignKey(ProjectExecution, on_delete=models.SET_NULL, blank=True, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, blank=True, null=True)
    channel = models.CharField(max_length=20, default='whatsapp')
    direction = models.CharField(max_length=10, default='outbound')
    message_type = models.CharField(max_length=30, default='update')
    content = models.TextField()
    status = models.CharField(max_length=20, default='sent')
    response_time_seconds = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.name} {self.channel} {self.message_type}"


class ServiceCategory(models.Model):
    """Define service categories like CMS, Ecommerce, Flutter, Video, Design, AI, Hosting, etc."""
    name = models.CharField(max_length=100)  # e.g., "CMS Web Development", "Ecommerce"
    slug = models.SlugField(unique=True)  # e.g., "cms", "ecommerce"
    description = models.TextField()
    icon = models.CharField(max_length=50, blank=True, default='')  # e.g., emoji or icon class
    order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "Service Categories"

    def __str__(self):
        return self.name


class ServicePackage(models.Model):
    """Packages within a service category (e.g., 1-page vs 5-page for CMS)"""
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=120)  # e.g., "Basic 1-Page", "Professional 5-Page"
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    platform = models.CharField(max_length=50, blank=True, default='')  # e.g., "WordPress", "Shopify"
    features = models.TextField()  # JSON or line-separated features
    deliverables = models.TextField(blank=True, default='')  # What client gets
    timeline_days = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'ordering', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class ServiceAddOn(models.Model):
    """Add-ons that can be bundled with packages (e.g., SEO package, extra pages)"""
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='addons')
    name = models.CharField(max_length=120)  # e.g., "SEO Plus Package", "Extra Page"
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_unit = models.CharField(max_length=30, default='one-time')  # one-time, per-page, per-item, monthly
    max_quantity = models.PositiveIntegerField(blank=True, null=True)  # None = unlimited
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category.name} | {self.name} (${self.price})"


# Extend Lead model to track multi-service selections
# Note: In practice, you'd use Django migrations to add these fields to Lead:
# - service_category (ForeignKey to ServiceCategory)
# - selected_package (ForeignKey to ServicePackage)
# - selected_addons (ManyToManyField to ServiceAddOn)
# - service_specific_data (JSONField for storing service-specific collected info)