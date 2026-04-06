from datetime import timedelta

from django.utils import timezone

from .models import (
    CommunicationLog,
    FollowUpTask,
    Invoice,
    PaymentReminder,
    ProjectExecution,
    ProjectMilestone,
)


MILESTONE_TEMPLATES = [
    ('Content Setup', 1),
    ('Design', 2),
    ('Development', 3),
    ('Add-ons', 4),
    ('QA', 5),
    ('Review', 6),
]


def schedule_default_followups(lead):
    tasks = []
    for day_offset in (1, 3, 7):
        due_at = timezone.now() + timedelta(days=day_offset)
        tasks.append(
            FollowUpTask(
                lead=lead,
                day_offset=day_offset,
                due_at=due_at,
                status='pending',
                message=f'Follow-up day {day_offset} for lead qualification.',
            )
        )
    FollowUpTask.objects.bulk_create(tasks)



def log_communication(lead, content, message_type='update', direction='outbound', channel='whatsapp', project=None, invoice=None):
    return CommunicationLog.objects.create(
        lead=lead,
        project=project,
        invoice=invoice,
        channel=channel,
        direction=direction,
        message_type=message_type,
        content=content,
        status='sent',
    )



def create_invoice_from_quote(lead, quote, terms='Payment due in 7 days'):
    due_date = timezone.now().date() + timedelta(days=7)
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    invoice = Invoice.objects.create(
        lead=lead,
        quote=quote,
        invoice_number=f'INV-{lead.id}-{timestamp}',
        subtotal=quote.total_price,
        discount=0,
        surcharge=0,
        total_amount=quote.total_price,
        outstanding_balance=quote.total_price,
        payment_terms=terms,
        due_date=due_date,
        status='sent',
        sent_at=timezone.now(),
    )
    log_communication(
        lead=lead,
        invoice=invoice,
        channel='email',
        message_type='invoice_sent',
        content=f'Invoice {invoice.invoice_number} sent. Due {invoice.due_date}.',
    )
    return invoice



def send_payment_reminder(invoice, reminder_type='pre_due'):
    reminder = PaymentReminder.objects.create(
        invoice=invoice,
        reminder_type=reminder_type,
        channel='email',
        note=f'{reminder_type} reminder for {invoice.invoice_number}',
    )
    invoice.last_reminder_at = timezone.now()
    invoice.save(update_fields=['last_reminder_at'])
    log_communication(
        lead=invoice.lead,
        invoice=invoice,
        channel='email',
        message_type='payment_reminder',
        content=f'Reminder {reminder_type} sent for {invoice.invoice_number}.',
    )
    return reminder



def activate_project_after_payment(invoice):
    if invoice.status != 'paid':
        return None

    project, _ = ProjectExecution.objects.get_or_create(
        lead=invoice.lead,
        defaults={
            'invoice': invoice,
            'status': 'active',
            'start_date': timezone.now().date(),
            'expected_delivery': timezone.now().date() + timedelta(days=14),
            'is_priority': invoice.lead.timeline in ('fast', 'urgent'),
        },
    )

    if project.invoice_id != invoice.id:
        project.invoice = invoice
        project.save(update_fields=['invoice'])

    ensure_project_milestones(project)

    log_communication(
        lead=invoice.lead,
        project=project,
        invoice=invoice,
        message_type='project_activated',
        content='Project activated after payment confirmation.',
    )
    return project



def ensure_project_milestones(project):
    existing = set(project.projectmilestone_set.values_list('name', flat=True))
    to_create = []
    for name, order in MILESTONE_TEMPLATES:
        if name not in existing:
            to_create.append(
                ProjectMilestone(
                    project=project,
                    name=name,
                    order=order,
                    status='pending',
                )
            )
    if to_create:
        ProjectMilestone.objects.bulk_create(to_create)



def weekly_progress_update(project):
    pending_count = project.projectmilestone_set.filter(status='pending').count()
    completed_count = project.projectmilestone_set.filter(status='completed').count()
    content = (
        f'Weekly progress: {completed_count} milestones completed, '
        f'{pending_count} pending. Current status: {project.status}.'
    )
    return log_communication(
        lead=project.lead,
        project=project,
        message_type='weekly_progress',
        content=content,
    )
