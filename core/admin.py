from django.contrib import admin
from .models import (
	CommunicationLog,
	FollowUpTask,
	Invoice,
	Lead,
	Intake,
	PaymentReminder,
	ProjectExecution,
	ProjectMilestone,
	Quote,
	ServiceCategory,
	ServicePackage,
	ServiceAddOn,
)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'name',
		'location',
		'phone',
		'source',
		'source_campaign',
		'project_type',
		'primary_goal',
		'budget_range',
		'lead_score',
		'seriousness_level',
		'is_serious',
		'stage',
		'next_action',
		'recommended_service',
		'created_at',
	)
	list_filter = (
		'source',
		'source_detected_by',
		'project_type',
		'timeline',
		'stage',
		'seriousness_level',
		'is_serious',
		'needs_human',
		'business_ready',
		'is_decision_maker',
		'willing_to_call',
		'can_pay_deposit',
		'assets_ready',
		'logo_ready',
		'content_ready',
		'images_ready',
	)
	search_fields = (
		'name',
		'location',
		'email',
		'phone',
		'business_name',
		'source_campaign',
		'client_need',
		'client_need_details',
		'expected_benefit',
		'expected_benefit_details',
		'first_message',
		'first_message_summary',
		'current_presence_link',
		'next_action',
		'recommended_service',
	)
	readonly_fields = ('created_at',)
	fieldsets = (
		('Contact', {
			'fields': ('name', 'location', 'email', 'phone', 'source', 'source_campaign', 'source_detected_by')
		}),
		('Need & Qualification', {
			'fields': (
				'project_type',
				'primary_goal',
				'business_name',
				'first_message',
				'first_message_summary',
				'current_presence_link',
				'client_need',
				'client_need_details',
				'expected_benefit',
				'expected_benefit_details',
				'budget_range',
				'is_decision_maker',
				'business_ready',
				'willing_to_call',
				'can_pay_deposit',
				'assets_ready',
				'logo_ready',
				'content_ready',
				'images_ready',
			)
		}),
		('Workflow', {
			'fields': (
				'timeline',
				'contact_preference',
				'stage',
				'lead_score',
				'seriousness_level',
				'next_action',
				'is_serious',
				'needs_human',
				'recommended_service',
				'disqualification_reason',
				'rough_price',
				'created_at',
			)
		}),
	)


@admin.register(Intake)
class IntakeAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'lead',
		'pages',
		'ecommerce_platform',
		'ai_package',
		'custom_package',
		'timeline_confirm',
		'is_complete',
		'created_at',
	)
	list_filter = ('timeline_confirm', 'is_complete', 'ecommerce_platform', 'ai_package', 'custom_package')
	search_fields = ('lead__name', 'lead__phone', 'addons', 'integrations')
	readonly_fields = ('created_at',)


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
	list_display = ('id', 'intake', 'total_price', 'monthly_cost', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('intake__lead__name', 'intake__lead__phone', 'breakdown', 'notes')
	readonly_fields = ('created_at',)


@admin.register(FollowUpTask)
class FollowUpTaskAdmin(admin.ModelAdmin):
	list_display = ('id', 'lead', 'day_offset', 'due_at', 'status', 'created_at')
	list_filter = ('status', 'day_offset')
	search_fields = ('lead__name', 'lead__phone', 'message')
	readonly_fields = ('created_at',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
	list_display = ('id', 'invoice_number', 'lead', 'total_amount', 'outstanding_balance', 'status', 'due_date', 'created_at')
	list_filter = ('status', 'due_date', 'created_at')
	search_fields = ('invoice_number', 'lead__name', 'lead__phone')
	readonly_fields = ('created_at',)


@admin.register(PaymentReminder)
class PaymentReminderAdmin(admin.ModelAdmin):
	list_display = ('id', 'invoice', 'reminder_type', 'channel', 'sent_at')
	list_filter = ('reminder_type', 'channel')
	search_fields = ('invoice__invoice_number', 'note')


@admin.register(ProjectExecution)
class ProjectExecutionAdmin(admin.ModelAdmin):
	list_display = ('id', 'lead', 'status', 'is_priority', 'assigned_to', 'start_date', 'expected_delivery')
	list_filter = ('status', 'is_priority')
	search_fields = ('lead__name', 'lead__phone', 'assigned_to')
	readonly_fields = ('created_at',)


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
	list_display = ('id', 'project', 'name', 'order', 'status', 'eta', 'completed_at')
	list_filter = ('status', 'name')
	search_fields = ('project__lead__name', 'name', 'client_update')


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
	list_display = ('id', 'lead', 'channel', 'direction', 'message_type', 'status', 'created_at')
	list_filter = ('channel', 'direction', 'message_type', 'status')
	search_fields = ('lead__name', 'lead__phone', 'content')
	readonly_fields = ('created_at',)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'slug', 'icon', 'order', 'is_active')
	list_filter = ('is_active', 'order')
	search_fields = ('name', 'slug', 'description')
	prepopulated_fields = {'slug': ('name',)}


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
	list_display = ('id', 'category', 'name', 'platform', 'base_price', 'timeline_days', 'is_active')
	list_filter = ('category', 'is_active', 'platform')
	search_fields = ('name', 'description', 'category__name')
	readonly_fields = ('created_at',)


@admin.register(ServiceAddOn)
class ServiceAddOnAdmin(admin.ModelAdmin):
	list_display = ('id', 'category', 'name', 'price', 'price_unit', 'max_quantity', 'is_active')
	list_filter = ('category', 'is_active', 'price_unit')
	search_fields = ('name', 'description', 'category__name')
	readonly_fields = ('created_at',)