import re

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from .forms import SalesForm, IntakeForm
from .models import Invoice, Lead, Intake, ProjectExecution, Quote
from .rules import (
    calculate_quote,
    evaluate_lead,
    recommend_service,
    rough_range_for_project,
)
from .workflow import (
    activate_project_after_payment,
    create_invoice_from_quote,
    log_communication,
    schedule_default_followups,
    weekly_progress_update,
)


def detect_source(request):
    explicit = (request.GET.get('utm_source') or request.GET.get('src') or '').lower().strip()
    campaign = (request.GET.get('utm_campaign') or '').strip()

    known_sources = {'facebook', 'whatsapp', 'instagram', 'google', 'website', 'referral'}
    if explicit in known_sources:
        return explicit, campaign, 'url'

    ref = (request.META.get('HTTP_REFERER') or '').lower()
    if 'facebook.com' in ref or 'fb.' in ref:
        return 'facebook', campaign, 'referrer'
    if 'instagram.com' in ref:
        return 'instagram', campaign, 'referrer'


    if 'wa.me' in ref or 'whatsapp' in ref:
        return 'whatsapp', campaign, 'referrer'
    if 'google.' in ref:
        return 'google', campaign, 'referrer'

    return 'other', campaign, 'auto'


def summarize_first_message(first_message):
    msg = " ".join(first_message.strip().split())
    if len(msg) <= 180:
        return msg
    return f"{msg[:177]}..."


CHAT_STEPS = [
    {
        'field': 'name',
        'required': True,
        'prompt': {
            'en': 'What is your full name?',
            'nl': 'Wat is uw volledige naam?',
        },
    },
    {
        'field': 'email',
        'required': True,
        'prompt': {
            'en': 'What is your email address?',
            'nl': 'Wat is uw e-mailadres?',
        },
    },
    {
        'field': 'phone',
        'required': True,
        'prompt': {
            'en': 'And your phone number?',
            'nl': 'En uw telefoonnummer?',
        },
    },
    {
        'field': 'project_type',
        'required': True,
        'prompt': {
            'en': 'Sure. Is this mainly for a website, e-commerce store, AI system, or custom software?',
            'nl': 'Prima. Is dit vooral voor een website, e-commerce winkel, AI-systeem of maatwerksoftware?',
        },
        'quick_replies': [
            ('cms', 'Website'),
            ('ecommerce', 'E-commerce Store'),
            ('ai', 'AI System'),
            ('custom', 'CRM / ERP / Custom Software'),
            ('custom', 'Not Sure - Guide Me'),
        ],
    },
    {
        'field': 'expected_benefit',
        'required': True,
        'prompt': {
            'en': 'Got it. What is your main goal with this project?',
            'nl': 'Begrepen. Wat is uw hoofddoel met dit project?',
        },
        'quick_replies': [
            ('increase_sales', 'Increase Sales / Revenue'),
            ('lead_generation', 'Generate Leads / Inquiries'),
            ('brand_awareness', 'Online Presence / Branding'),
            ('automation', 'Automation / Save Time'),
            ('better_support', 'Better Customer Support'),
            ('credibility', 'Build Credibility / Trust'),
        ],
    },
    {
        'field': 'selected_features',
        'required': True,
        'prompt': {
            'en': 'Would you like any add-ons? Pick one or skip.',
            'nl': 'Wilt u add-ons? Kies er een of sla over.',
        },
        'quick_replies': [
            ('none', 'No Add-on'),
            ('seo_pro', 'SEO Pro (+$150)'),
            ('booking_system', 'Booking System (+$100)'),
            ('speed_optimization', 'Speed Boost (+$75)'),
            ('security', 'Security Package (+$50)'),
            ('analytics', 'Analytics Setup (+$50)'),
            ('social_integration', 'Social Media Links (+$25)'),
        ],
    },
    {
        'field': 'content_delivery',
        'required': True,
        'prompt': {
            'en': 'Who will provide the content (text, images, etc.)?',
            'nl': 'Wie levert de content (tekst, afbeeldingen, etc.)?',
        },
        'quick_replies': [
            ('client_provides', 'I Will Provide'),
            ('we_create', 'You Create (+20%)'),
            ('mixed', 'Some of Both'),
            ('not_sure', 'Not Sure Yet'),
        ],
    },
    {
        'field': 'budget_range',
        'required': True,
        'prompt': {
            'en': 'What budget range feels realistic right now?',
            'nl': 'Welk budgetbereik voelt nu realistisch?',
        },
        'quick_replies': [
            ('very_low', 'Under $150'),
            ('low', '$150 - $300'),
            ('mid', '$300 - $1000'),
            ('high', '$1000 - $3000'),
            ('premium', 'Above $3000'),
            ('undecided', 'Not Sure Yet'),
        ],
    },
    {
        'field': 'timeline',
        'required': True,
        'prompt': {
            'en': 'How soon do you need this completed?',
            'nl': 'Hoe snel heeft u dit nodig?',
        },
        'quick_replies': [
            ('relaxed', 'Flexible / No Rush (2-4 weeks)'),
            ('normal', 'Normal (1-2 weeks)'),
            ('fast', 'Fast (3-5 days)'),
            ('urgent', 'Urgent (1-2 days) +$50'),
        ],
    },
    {
        'field': 'is_decision_maker',
        'required': False,
        'prompt': {
            'en': 'Optional: Are you the decision maker?',
            'nl': 'Optioneel: Bent u de beslisser?',
        },
        'quick_replies': [('yes', 'Yes'), ('no', 'No'), ('skip', 'Skip')],
    },
    {
        'field': 'can_pay_deposit',
        'required': False,
        'prompt': {
            'en': 'Optional: Can you pay a deposit to start?',
            'nl': 'Optioneel: Kunt u een aanbetaling doen om te starten?',
        },
        'quick_replies': [('yes', 'Yes'), ('no', 'No'), ('skip', 'Skip')],
    },
    {
        'field': 'willing_to_call',
        'required': False,
        'prompt': {
            'en': 'Optional: Are you available for a quick call?',
            'nl': 'Optioneel: Bent u beschikbaar voor een kort gesprek?',
        },
        'quick_replies': [('yes', 'Yes'), ('no', 'No'), ('skip', 'Skip')],
    },
]

MANDATORY_FIELDS = [
    'name',
    'email',
    'phone',
    'project_type',
    'expected_benefit',
    'selected_features',
    'content_delivery',
    'budget_range',
    'timeline',
]

OPTIONAL_FIELDS = [
    'is_decision_maker',
    'can_pay_deposit',
    'willing_to_call',
]

FIELD_LABELS = {
    'name': 'full name',
    'email': 'email address',
    'phone': 'phone number',
    'project_type': 'project type',
    'expected_benefit': 'main goal',
    'selected_features': 'add-ons',
    'content_delivery': 'content responsibility',
    'budget_range': 'budget range',
    'timeline': 'timeline',
    'service_plan': 'plan',
    'contact_preference': 'contact preference',
    'is_decision_maker': 'decision maker',
    'can_pay_deposit': 'deposit readiness',
    'willing_to_call': 'call readiness',
}

NON_NAME_VALUES = {
    'cms', 'ecommerce', 'ai', 'flutter', 'custom', 'video', 'design', 'social', 'hosting',
    'urgent', 'fast', 'normal', 'yes', 'no', 'skip', 'low', 'mid', 'high', 'undecided',
}

FIELD_CONFIG = {step['field']: step for step in CHAT_STEPS}

STEP_PROMPT_ES = {
    'name': 'Bienvenido a Divi Hosting. Cual es tu nombre completo?',
    'email': 'Cual es tu correo electronico?',
    'phone': 'Comparte tu numero de telefono para continuar.',
    'project_type': 'Es para sitio web, ecommerce, AI o software personalizado?',
    'expected_benefit': 'Cual es tu objetivo principal ahora?',
    'selected_features': 'Elige un add-on principal o ninguno.',
    'content_delivery': 'Quien aporta el contenido y recursos?',
    'budget_range': 'Que rango de presupuesto te resulta posible ahora?',
    'timeline': 'Que tan urgente es tu proyecto?',
    'is_decision_maker': 'Opcional: Eres la persona que toma la decision final?',
    'can_pay_deposit': 'Opcional: Puedes pagar un deposito para empezar?',
    'willing_to_call': 'Opcional: Estas disponible para una llamada rapida?',
}

STEP_REASON_TEXT = {
    'name': {
        'en': 'This helps us personalize your quote.',
        'nl': 'Dit helpt ons uw offerte te personaliseren.',
        'es': 'Esto nos ayuda a personalizar tu cotizacion.',
    },
    'phone': {
        'en': 'We use this only for project follow-up.',
        'nl': 'We gebruiken dit alleen voor projectopvolging.',
        'es': 'Lo usamos solo para seguimiento del proyecto.',
    },
    'email': {
        'en': 'We will send your quote to this email.',
        'nl': 'We sturen uw offerte naar dit e-mailadres.',
        'es': 'Enviaremos tu cotizacion a este correo.',
    },
}

INVALID_HINTS = {
    'name': {
        'en': 'Please enter your full name (for example: Unisha Perera).',
        'nl': 'Vul uw volledige naam in (bijvoorbeeld: Unisha Perera).',
        'es': 'Ingresa tu nombre completo (por ejemplo: Unisha Perera).',
    },
    'phone': {
        'en': 'Please enter a valid phone (for example: +5971234567 or 9865338866).',
        'nl': 'Vul een geldig telefoonnummer in (bijvoorbeeld: +31612345678).',
        'es': 'Ingresa un telefono valido (por ejemplo: +5971234567).',
    },
    'email': {
        'en': 'Please enter a valid email (for example: name@email.com).',
        'nl': 'Vul een geldig e-mailadres in (bijvoorbeeld: naam@email.com).',
        'es': 'Ingresa un correo valido (por ejemplo: nombre@email.com).',
    },
    'project_type': {
        'en': 'Please choose one recommended option below.',
        'nl': 'Kies een projecttype via de knoppen hieronder.',
        'es': 'Elige un tipo de proyecto con los botones de abajo.',
    },
    'business_ready': {
        'en': 'Please choose Yes, No, or Planning to start.',
        'nl': 'Kies Ja, Nee of Ik ga starten.',
        'es': 'Elige Si, No o Planeando comenzar.',
    },
    'customer_source': {
        'en': 'Please choose your current customer source from the options below.',
        'nl': 'Kies uw huidige klantenbron uit de opties hieronder.',
        'es': 'Elige tu fuente actual de clientes en las opciones abajo.',
    },
}

INTAKE_STAGES = [
    {
        'key': 'identity',
        'fields': ['name', 'email', 'phone'],
        'prompt': {
            'en': 'Let us start with identity details first.',
            'nl': 'Laten we eerst starten met identiteitsgegevens.',
        },
    },
    {
        'key': 'project_understanding',
        'fields': ['project_type', 'expected_benefit'],
        'prompt': {
            'en': 'Now we clarify project type and main goal.',
            'nl': 'Nu verduidelijken we projecttype en hoofddoel.',
        },
    },
    {
        'key': 'service_mapping',
        'fields': ['selected_features', 'content_delivery'],
        'prompt': {
            'en': 'Then we map practical service options.',
            'nl': 'Daarna mappen we praktische service-opties.',
        },
    },
    {
        'key': 'budget_timeline',
        'fields': ['budget_range', 'timeline'],
        'prompt': {
            'en': 'Finally we validate budget and timeline.',
            'nl': 'Tot slot valideren we budget en planning.',
        },
    },
]


def initial_assistant_state():
    return {
        'step_index': 0,
        'answered_fields': [],
        'completed_lead_id': None,
        'collected': {
            'primary_goal': 'website_presence',
            'logo_ready': False,
            'content_ready': False,
            'images_ready': False,
            'assets_ready': False,
            'current_presence_link': '',
            'business_name': '',
            'client_need_details': '',
            'expected_benefit_details': '',
            'service_plan': '',
            'selected_features': '',
            'content_delivery': '',
            'budget_range': '',
            'timeline': '',
        },
        'lang': 'en',
        'first_user_message': '',
        'source_override': '',
        'seen_intro': False,
        'awaiting_confirmation': False,
        'awaiting_edit_choice': False,
        'awaiting_csat': False,
        'awaiting_csat_comment': False,
        'csat_lead_id': None,
        'awaiting_post_save_choice': False,
        'awaiting_start_confirmation': True,
        'awaiting_bulk_contact': False,
        'awaiting_budget_resolution': False,
        # NEW: Production-level tracking
        'budget_retry_count': 0,
        'invalid_input_count': 0,
        'locked_fields': [],  # Fields that cannot be changed without explicit edit
        'risk_flags': [],  # Detected risk factors
        'rough_price_shown': False,
        'exact_quote_ready': False,
    }


@ensure_csrf_cookie
def assistant_view(request):
    return render(request, 'assistant.html')


@require_POST
def assistant_reset_api(request):
    request.session['assistant_state'] = initial_assistant_state()
    request.session.pop('lead_id', None)
    request.session.pop('rough_price', None)
    return JsonResponse({'ok': True})


def detect_language(text):
    lower = (text or '').lower()
    dutch_markers = [' wat ', ' ik ', ' geen ', ' met ', ' voor ', 'hallo', 'goedemiddag']
    if any(marker in f" {lower} " for marker in dutch_markers):
        return 'nl'
    spanish_markers = [' hola ', ' necesito ', ' presupuesto ', ' proyecto ', ' sitio web ', ' tienda ', 'gracias']
    if any(marker in f" {lower} " for marker in spanish_markers):
        return 'es'
    english_markers = [' hello ', ' hi ', ' quote ', ' project ', ' website ', ' pricing ', ' thanks ']
    if any(marker in f" {lower} " for marker in english_markers):
        return 'en'
    return None


def t(lang, en_text, nl_text, es_text=None):
    if lang == 'nl':
        return nl_text
    if lang == 'es' and es_text:
        return es_text
    return en_text


def translated(lang, en_text, nl_text, es_text=None):
    return t(lang, en_text, nl_text, es_text)


def name_from_state(state):
    return (state.get('collected', {}).get('name') or '').strip()


def ensure_assistant_state(state):
    state = state or {}
    state.setdefault('collected', {})
    state.setdefault('answered_fields', [])
    state.setdefault('lang', 'en')
    state.setdefault('first_user_message', '')
    state.setdefault('source_override', '')
    state.setdefault('seen_intro', False)
    state.setdefault('completed_lead_id', None)
    state.setdefault('awaiting_confirmation', False)
    state.setdefault('awaiting_edit_choice', False)
    state.setdefault('awaiting_csat', False)
    state.setdefault('awaiting_csat_comment', False)
    state.setdefault('csat_lead_id', None)
    state.setdefault('awaiting_post_save_choice', False)
    state.setdefault('awaiting_start_confirmation', True)
    state.setdefault('awaiting_bulk_contact', False)
    state.setdefault('awaiting_budget_resolution', False)
    # NEW: Production-level tracking
    state.setdefault('budget_retry_count', 0)
    state.setdefault('invalid_input_count', 0)
    state.setdefault('locked_fields', [])
    state.setdefault('risk_flags', [])
    state.setdefault('rough_price_shown', False)
    state.setdefault('exact_quote_ready', False)
    collected = state.setdefault('collected', {})
    collected.setdefault('budget_range', '')
    collected.setdefault('selected_features', '')
    collected.setdefault('timeline', '')
    sync_step_index(state)
    return state


# =============================================================================
# PRODUCTION-LEVEL VALIDATORS & PROCESSORS
# =============================================================================

MAX_BUDGET_RETRIES = 2
MAX_INVALID_RETRIES = 3
MIN_READINESS_PERCENT = 70

def strict_validate_field(field, value):
    """
    Strict validation returning (is_valid, error_message).
    Rejects invalid data with helpful guidance.
    """
    value = (value or '').strip()
    
    if field == 'name':
        if len(value) < 2:
            return False, 'Please enter your full name (at least 2 characters).'
        if not re.match(r"^[a-zA-Z][a-zA-Z\s\-']{1,60}$", value):
            return False, 'Name should contain only letters, spaces, or hyphens.'
        return True, ''
    
    if field == 'email':
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', value):
            return False, 'Please enter a valid email address (e.g., name@email.com).'
        return True, ''
    
    if field == 'phone':
        digits = re.sub(r'\D', '', value)
        if not (7 <= len(digits) <= 15):
            return False, 'Please enter a valid phone number (7-15 digits).'
        return True, ''
    
    if field == 'project_type':
        valid = {'cms', 'ecommerce', 'ai', 'flutter', 'custom', 'video', 'design', 'social', 'hosting'}
        if value not in valid:
            return False, 'Please select a project type from the options.'
        return True, ''
    
    if field == 'expected_benefit':
        valid = {'increase_sales', 'lead_generation', 'brand_awareness', 'automation', 'better_support', 'credibility'}
        if value not in valid:
            return False, 'Please select your main goal from the options.'
        return True, ''
    
    if field == 'selected_features':
        valid = {'none', 'seo_pro', 'booking_system', 'speed_optimization', 'security', 'analytics', 'social_integration'}
        if value not in valid:
            return False, 'Please select an add-on or choose No Add-on.'
        return True, ''
    
    if field == 'content_delivery':
        valid = {'client_provides', 'we_create', 'mixed', 'not_sure'}
        if value not in valid:
            return False, 'Please select who provides content.'
        return True, ''
    
    if field == 'budget_range':
        valid = {'very_low', 'low', 'mid', 'high', 'premium', 'undecided'}
        if value not in valid:
            return False, 'Please select a budget range from the options.'
        return True, ''
    
    if field == 'timeline':
        valid = {'relaxed', 'normal', 'fast', 'urgent'}
        if value not in valid:
            return False, 'Please select a timeline from the options.'
        return True, ''
    
    return True, ''


def calculate_readiness(state):
    """Calculate intake readiness percentage and return details."""
    collected = state.get('collected', {})
    total = len(MANDATORY_FIELDS)
    completed = sum(1 for f in MANDATORY_FIELDS if collected.get(f))
    percent = int((completed / total) * 100) if total > 0 else 0
    
    missing = [f for f in MANDATORY_FIELDS if not collected.get(f)]
    
    return {
        'percent': percent,
        'completed': completed,
        'total': total,
        'missing': missing,
        'ready': percent >= MIN_READINESS_PERCENT,
    }


def detect_risk_flags(state):
    """Detect risk factors that may prevent successful conversion."""
    risks = []
    collected = state.get('collected', {})
    
    # Budget risk
    budget = collected.get('budget_range')
    project = collected.get('project_type')
    if budget and project:
        check = budget_validation_result(collected)
        if not check.get('ok'):
            risks.append('BUDGET_TOO_LOW')
        elif budget == 'undecided':
            risks.append('BUDGET_UNCLEAR')
        elif budget == 'very_low':
            risks.append('BUDGET_MINIMAL')
    
    # Timeline pressure
    if collected.get('timeline') == 'urgent':
        risks.append('TIMELINE_URGENT')
    
    # Content risk
    if collected.get('content_delivery') == 'not_sure':
        risks.append('CONTENT_UNCLEAR')
    
    # High-value project without clear goal
    if project in ('custom', 'ecommerce', 'ai') and not collected.get('expected_benefit'):
        risks.append('GOAL_UNCLEAR')
    
    return risks


def get_rough_price_range(project_type):
    """Get rough price range after project type selection."""
    ranges = {
        'cms': {'min': 149, 'max': 599, 'label': '$149 - $599'},
        'ecommerce': {'min': 700, 'max': 3000, 'label': '$700 - $3,000'},
        'ai': {'min': 800, 'max': 1500, 'label': '$800 - $1,500+'},
        'flutter': {'min': 400, 'max': 1200, 'label': '$400 - $1,200'},
        'custom': {'min': 750, 'max': 4000, 'label': '$750 - $4,000+'},
        'video': {'min': 75, 'max': 300, 'label': '$75 - $300'},
        'design': {'min': 30, 'max': 200, 'label': '$30 - $200'},
        'social': {'min': 75, 'max': 400, 'label': '$75 - $400'},
        'hosting': {'min': 5, 'max': 250, 'label': '$5 - $250/mo'},
    }
    return ranges.get(project_type, {'min': 149, 'max': 599, 'label': '$149 - $599'})


def calculate_exact_quote(collected):
    """Calculate exact quote after full intake."""
    project = collected.get('project_type', 'cms')
    timeline = collected.get('timeline', 'normal')
    features = collected.get('selected_features', 'none')
    content = collected.get('content_delivery', 'mixed')
    
    # Base prices
    bases = {
        'cms': 149, 'ecommerce': 700, 'ai': 800, 'flutter': 400,
        'custom': 750, 'video': 75, 'design': 30, 'social': 75, 'hosting': 5,
    }
    base = bases.get(project, 149)
    
    # Content surcharge
    content_add = int(base * 0.2) if content == 'we_create' else 0
    
    # Feature prices
    feature_prices = {
        'seo_pro': 150, 'booking_system': 100, 'speed_optimization': 75,
        'security': 50, 'analytics': 50, 'social_integration': 25, 'none': 0,
    }
    addon = feature_prices.get(features, 0)
    
    # Timeline multipliers
    multipliers = {'relaxed': 0.95, 'normal': 1.0, 'fast': 1.25, 'urgent': 1.5}
    mult = multipliers.get(timeline, 1.0)
    
    subtotal = base + content_add + addon
    total = round(subtotal * mult)
    
    return {
        'base': base,
        'content_surcharge': content_add,
        'addon': addon,
        'timeline_multiplier': mult,
        'subtotal': subtotal,
        'total': total,
    }


def parse_freeform_intent(text, state):
    """
    Advanced intent extraction from freeform text.
    Parses multiple fields from a single natural sentence.
    """
    extracted = {}
    lower = (text or '').lower()
    
    # Extract project type
    project = extract_project_type(text)
    if project and not state.get('collected', {}).get('project_type'):
        extracted['project_type'] = project
    
    # Extract goal
    goal = extract_expected_benefit(text)
    if goal and not state.get('collected', {}).get('expected_benefit'):
        extracted['expected_benefit'] = goal
    
    # Extract features from natural language
    feature = extract_selected_feature(text)
    if feature and not state.get('collected', {}).get('selected_features'):
        extracted['selected_features'] = feature
    
    # Extract budget hints
    budget = extract_budget_range(text)
    if budget and not state.get('collected', {}).get('budget_range'):
        extracted['budget_range'] = budget
    
    # Extract timeline hints
    timeline = extract_timeline(text)
    if timeline and not state.get('collected', {}).get('timeline'):
        extracted['timeline'] = timeline
    
    # Extract content delivery
    content = extract_content_delivery(text)
    if content and not state.get('collected', {}).get('content_delivery'):
        extracted['content_delivery'] = content
    
    return extracted


def step_prompt_text(step, lang):
    field = step['field']
    if lang == 'es':
        return step['prompt'].get('es', STEP_PROMPT_ES.get(field, step['prompt'].get('en', '')))
    return step['prompt'].get(lang, step['prompt'].get('en', ''))


def progress_snapshot(state):
    completed = sum(1 for field in MANDATORY_FIELDS if is_field_complete(state, field))
    total = len(MANDATORY_FIELDS)
    if completed < 3:
        text = 'Discovery in progress'
    elif completed < total:
        text = 'Building your recommendation'
    else:
        text = 'Plan ready to send'
    return {
        'completed': completed,
        'total': total,
        'text': text,
    }


def invalid_step_message(step, lang):
    field = step['field']
    hint = INVALID_HINTS.get(field, {})
    if lang == 'es':
        return hint.get('es', hint.get('en', 'Thanks. Choose the closest option below and I will adapt.'))
    if lang == 'nl':
        return hint.get('nl', hint.get('en', 'Dank u. Kies hieronder de dichtstbijzijnde optie en ik pas me aan.'))
    return hint.get('en', 'Thanks. Choose the closest option below and I will adapt.')


def intake_review_lines(state):
    collected = state.get('collected', {})
    return [
        f"Name: {collected.get('name', '-')}",
        f"Email: {collected.get('email', '-')}",
        f"Phone: {collected.get('phone', '-')}",
        f"Project type: {collected.get('project_type', '-')}",
        f"Goal: {collected.get('expected_benefit', '-')}",
        f"Add-on: {collected.get('selected_features', '-')}",
        f"Content: {collected.get('content_delivery', '-')}",
        f"Budget range: {collected.get('budget_range', '-')}",
        f"Timeline: {collected.get('timeline', '-')}",
    ]


def edit_choice_quick_replies():
    return [(f"edit:{field}", field_label(field).title()) for field in MANDATORY_FIELDS]


def service_plan_quick_replies(project_type):
    options = {
        'cms': [
            '1-Page Website (WordPress)',
            '5-Page Website (WordPress)',
            '1-Page Website (Wix)',
            '5-Page Website (Wix)',
            '1-Page Website (Squarespace)',
            '5-Page Website (Squarespace)',
            '1-Page Website (Webflow)',
            '5-Page Website (Webflow)',
        ],
        'ecommerce': ['WooCommerce Basic Store', 'Magento 2 Basic'],
        'ai': ['AI Chat Assistant', 'AI Booking Assistant', 'AI Business Assistant'],
        'flutter': ['Corporate App (Android & iOS)', 'Booking App (Android & iOS)'],
        'custom': ['CRM System', 'ERP System'],
        'video': ['Video Editing (30 sec)', 'Animation Video'],
        'design': ['AI Logo Design', 'Basic Logo Design', 'Custom Logo Design'],
        'social': ['Campaign Setup', 'Basic Monthly', 'Standard Monthly', 'Advanced Monthly'],
        'hosting': [
            'Shared Hosting Basic',
            'Shared Hosting E-commerce',
            'Shared Hosting Plus',
            'VPS',
            'VPS Plus',
            'Dedicated Basic',
            'Dedicated Plus',
            'Dedicated Pro',
            'Dedicated Advance',
        ],
    }
    return [(name, name) for name in options.get(project_type, [])]


SERVICE_PRICING_RANGES = {
    'cms': '$149 - $1200',
    'ecommerce': '$700 - $3000',
    'ai': '$800 - $1500+',
    'custom': '$750 - $4000+',
}


def recommend_solution(collected):
    project_type = collected.get('project_type', '')
    goal = collected.get('expected_benefit')
    budget = collected.get('budget_range', 'undecided')

    if project_type == 'custom' and budget == 'low':
        return {
            'project_type': 'cms',
            'primary_label': 'Website Foundation',
            'secondary': ('custom', 'Custom System Later Phase'),
            'reason': 'Custom systems typically start higher, so a website-first path is safer for this budget.',
            'price_range': SERVICE_PRICING_RANGES['cms'],
        }

    if project_type == 'ecommerce' and budget == 'low':
        return {
            'project_type': 'cms',
            'primary_label': 'Website + Product Showcase',
            'secondary': ('ecommerce', 'E-commerce Phase 2 Plan'),
            'reason': 'With low budget, start with visibility and validation before full store build.',
            'price_range': SERVICE_PRICING_RANGES['cms'],
        }

    if goal == 'automation' and budget in {'low', 'undecided'}:
        return {
            'project_type': 'cms',
            'primary_label': 'Website + Lead Flow Starter',
            'secondary': ('ai', 'Automation Upgrade Path'),
            'reason': 'Automation works best after a stable intake and lead pipeline is live.',
            'price_range': SERVICE_PRICING_RANGES['cms'],
        }

    return {
        'project_type': project_type or 'cms',
        'primary_label': {
            'cms': 'Website + Lead Capture',
            'ecommerce': 'Online Store Setup',
            'ai': 'AI Assistant Setup',
            'custom': 'Custom Business System',
        }.get(project_type or 'cms', 'Website + Lead Capture'),
        'secondary': ('custom', 'Guided Alternative Path'),
        'reason': 'This aligns with your selected service direction and current objective.',
        'price_range': SERVICE_PRICING_RANGES.get(project_type or 'cms', SERVICE_PRICING_RANGES['cms']),
    }


def project_type_quick_replies(state):
    return [
        ('cms', 'Website + Lead Capture'),
        ('ecommerce', 'Online Store Setup'),
        ('ai', 'AI Assistant Setup'),
        ('custom', 'Custom Business System'),
    ]


SERVICE_MINIMUM_PRICE = {
    'cms': 149,
    'ecommerce': 700,
    'ai': 800,
    'custom': 750,
}


def budget_ceiling(budget_range):
    mapping = {
        'very_low': 150,
        'low': 300,
        'mid': 1000,
        'high': 3000,
        'premium': 10**9,
        'undecided': None,
    }
    return mapping.get(budget_range)


def budget_validation_result(collected):
    project_type = collected.get('project_type')
    budget_range = collected.get('budget_range')
    if not project_type or not budget_range:
        return {'ok': True}
    minimum = SERVICE_MINIMUM_PRICE.get(project_type, 149)
    ceiling = budget_ceiling(budget_range)
    if ceiling is None:
        return {'ok': True}
    if minimum > ceiling:
        return {
            'ok': False,
            'minimum': minimum,
            'ceiling': ceiling,
            'project_type': project_type,
        }
    return {'ok': True}


def recommendation_message(state, lang):
    rec = recommend_solution(state.get('collected', {}))
    return t(
        lang,
        f"Nice, that helps. Based on your situation, I recommend: {rec['primary_label']}. Why: {rec['reason']} Estimated range: {rec['price_range']}",
        f"Top, dit helpt. Op basis van uw situatie adviseer ik: {rec['primary_label']}. Waarom: {rec['reason']} Indicatie: {rec['price_range']}",
        f"Perfecto, esto ayuda. Segun tu situacion, recomiendo: {rec['primary_label']}. Motivo: {rec['reason']} Rango estimado: {rec['price_range']}",
    )


def business_insight_for_next_step(state, next_step, lang):
    """
    Returns a brief contextual tip (no "Business insight:" prefix).
    Empty for contact fields to avoid clutter.
    """
    if not next_step:
        return ''  # No insight needed at confirmation stage
    
    field = next_step['field']
    # Skip insights for basic contact fields
    if field in {'name', 'email', 'phone', 'contact_preference'}:
        return ''
    
    # Concise tips only for key decision fields
    tips = {
        'expected_benefit': t(lang, 'This shapes your strategy.', 'Dit bepaalt uw strategie.', 'Esto define tu estrategia.'),
        'budget_range': t(lang, 'Keeps recommendations practical.', 'Houdt aanbevelingen praktisch.', 'Mantiene las recomendaciones practicas.'),
        'project_type': t(lang, '', '', ''),  # No tip needed, question is clear
        'timeline': t(lang, '', '', ''),
    }
    return tips.get(field, '')


def compose_guided_message(base_message, insight):
    if not insight:
        return base_message
    if not base_message:
        return insight
    return f"{base_message} {insight}"  # Single line, no double newline


def mark_field_answered(state, field):
    answered = state.setdefault('answered_fields', [])
    if field not in answered:
        answered.append(field)


def is_field_complete(state, field):
    collected = state.get('collected', {})
    if field in OPTIONAL_FIELDS:
        return field in state.get('answered_fields', [])
    value = collected.get(field)
    return value not in (None, '', [])


def missing_fields(state, fields):
    return [field for field in fields if not is_field_complete(state, field)]


def current_stage(state):
    for stage in INTAKE_STAGES:
        missing = missing_fields(state, stage['fields'])
        if missing:
            return stage, missing
    return None, []


def field_label(field):
    return FIELD_LABELS.get(field, field.replace('_', ' '))


def format_field_list(fields):
    labels = [field_label(field) for field in fields]
    if not labels:
        return ''
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f'{labels[0]} and {labels[1]}'
    return ', '.join(labels[:-1]) + f', and {labels[-1]}'


def prompt_for_step(step, lang, state):
    pending_risk_field = pending_risk_check_field(state, analyze_process_state(state.get('collected', {})))
    if pending_risk_field:
        risk_step = FIELD_CONFIG[pending_risk_field]
        return step_prompt_text(risk_step, lang)

    if not step:
        return t(
            lang,
            'Mandatory intake is complete. Optional extras are still welcome: decision maker, deposit, and call readiness.',
            'De verplichte intake is compleet. Optionele extra informatie blijft welkom: beslisser, aanbetaling en gespreksbereidheid.',
            'La toma obligatoria esta completa. Aun puedes agregar datos opcionales: decision, deposito y llamada.',
        )
    prompt = step_prompt_text(step, lang)
    if step['field'] in {'name', 'email', 'phone'}:
        return prompt
    if step['field'] == 'project_type':
        return t(
            lang,
            'Which option sounds closer to what you need right now?',
            'Welke optie past nu het best bij wat u nodig heeft?',
            'Que opcion se acerca mas a lo que necesitas ahora?',
        )
    if step['field'] == 'service_plan':
        project_type = state.get('collected', {}).get('project_type', '')
        plan_titles = {
            'cms': {
                'en': 'Great. Which website plan matches your goal?',
                'nl': 'Prima. Welk websitepakket past bij uw doel?',
                'es': 'Perfecto. Que plan web encaja con tu objetivo?',
            },
            'ecommerce': {
                'en': 'Great. Which e-commerce setup do you want to start with?',
                'nl': 'Prima. Met welke e-commerce setup wilt u starten?',
                'es': 'Perfecto. Con que configuracion de e-commerce quieres empezar?',
            },
            'ai': {
                'en': 'Great. Which AI assistant setup fits your business best?',
                'nl': 'Prima. Welke AI-assistent setup past het best bij uw bedrijf?',
                'es': 'Perfecto. Que configuracion de asistente AI se adapta mejor a tu negocio?',
            },
            'flutter': {
                'en': 'Great. Which mobile app package do you need?',
                'nl': 'Prima. Welk mobiele-app pakket heeft u nodig?',
                'es': 'Perfecto. Que paquete de app movil necesitas?',
            },
            'custom': {
                'en': 'Great. Which custom development track is closest to your need?',
                'nl': 'Prima. Welk maatwerktraject past het best bij uw behoefte?',
                'es': 'Perfecto. Que tipo de desarrollo personalizado se acerca mas a tu necesidad?',
            },
            'video': {
                'en': 'Great. Which video service do you need first?',
                'nl': 'Prima. Welke videoservice heeft u als eerste nodig?',
                'es': 'Perfecto. Que servicio de video necesitas primero?',
            },
            'design': {
                'en': 'Great. Which design service should we start with?',
                'nl': 'Prima. Met welke ontwerpdienst zullen we starten?',
                'es': 'Perfecto. Con que servicio de diseno empezamos?',
            },
            'social': {
                'en': 'Great. Which social promotion plan do you prefer?',
                'nl': 'Prima. Welk social-promotion pakket heeft uw voorkeur?',
                'es': 'Perfecto. Que plan de promocion social prefieres?',
            },
            'hosting': {
                'en': 'Great. Which hosting plan do you want?',
                'nl': 'Prima. Welk hostingpakket wilt u?',
                'es': 'Perfecto. Que plan de hosting quieres?',
            },
        }
        category_prompt = plan_titles.get(project_type, {}).get(lang) or plan_titles.get(project_type, {}).get('en')
        if category_prompt:
            prompt = f"{category_prompt}"
    why = STEP_REASON_TEXT.get(step['field'], {}).get(lang) or STEP_REASON_TEXT.get(step['field'], {}).get('en', '')
    if why:
        if step['field'] == 'project_type':
            return prompt
        return f"{prompt} {why}"
    return prompt


def quick_replies_for_state(state):
    pending_risk_field = pending_risk_check_field(state, analyze_process_state(state.get('collected', {})))
    if pending_risk_field:
        return FIELD_CONFIG.get(pending_risk_field, {}).get('quick_replies', [])

    step = current_step(state)
    if not step:
        return []
    if step['field'] == 'project_type':
        return project_type_quick_replies(state)
    if step['field'] == 'service_plan':
        project_type = state.get('collected', {}).get('project_type', '')
        dynamic = service_plan_quick_replies(project_type)
        if dynamic:
            return dynamic
    return step.get('quick_replies', [])


def starter_quick_replies(lang='en'):
    return []


def current_step(state):
    for field in MANDATORY_FIELDS:
        if not is_field_complete(state, field):
            return FIELD_CONFIG[field]
    return None


def sync_step_index(state):
    step = current_step(state)
    if not step:
        state['step_index'] = len(MANDATORY_FIELDS)
        return
    state['step_index'] = MANDATORY_FIELDS.index(step['field'])


def normalize_input(value):
    return (value or '').strip()


def validate_step(step, value):
    field = step['field']
    v = normalize_input(value)

    if field == 'email':
        return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v))
    if field == 'phone':
        return bool(re.match(r'^\+?[0-9\-\s]{7,20}$', v))
    if field in ('project_type', 'expected_benefit', 'business_ready', 'customer_source', 'budget_range', 'timeline', 'contact_preference', 'content_delivery', 'selected_features'):
        if field == 'project_type':
            allowed = {k for k, _ in project_type_quick_replies({'collected': step.get('_state_collected', {})})}
            if not allowed:
                allowed = {k for k, _ in step.get('quick_replies', [])}
        else:
            allowed = {k for k, _ in step.get('quick_replies', [])}
        return v in allowed
    if field in ('is_decision_maker', 'can_pay_deposit', 'willing_to_call'):
        return v in {'yes', 'no', 'skip'}
    return len(v) >= 2


def parse_value(field, value):
    v = normalize_input(value)
    if field == 'name':
        return extract_name(v)
    if field == 'business_ready':
        return v
    if field in ('is_decision_maker', 'can_pay_deposit', 'willing_to_call'):
        if v == 'skip':
            return None
        if v == 'yes':
            return True
        return False
    return v


def extract_name(text):
    lower = text.lower().strip()
    patterns = [
        r"(?:my name is|i am|i'm)\s+([a-zA-Z][a-zA-Z\s\-']{1,60})",
        r"(?:this is)\s+([a-zA-Z][a-zA-Z\s\-']{1,60})",
    ]
    for pattern in patterns:
        m = re.search(pattern, lower)
        if m:
            candidate = m.group(1)
            candidate = re.split(r"\band\b|\bi want\b|\bneed\b|\bfor\b", candidate)[0].strip()
            words = [w for w in re.split(r"\s+", candidate) if w]
            if words:
                return " ".join(words[:3]).title()

    cleaned = re.sub(r"[^a-zA-Z\s\-']", "", text).strip()
    words = [w for w in cleaned.split() if w.lower() not in {'my', 'name', 'is', 'i', 'am', 'im', 'this', 'hey', 'hi', 'hello'}]
    if not words:
        return text[:60].strip()
    return " ".join(words[:3]).title()


def extract_email(text):
    match = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text or '')
    return match.group(1).lower() if match else ''


def normalize_phone(value):
    value = (value or '').strip()
    if value.startswith('+'):
        return '+' + re.sub(r'\D', '', value[1:])
    return re.sub(r'\D', '', value)


def extract_phone(text):
    matches = re.findall(r'(?<!\w)(\+?[0-9][0-9\-\s]{6,18}[0-9])(?!\w)', text or '')
    for candidate in matches:
        normalized = normalize_phone(candidate)
        digits_only = re.sub(r'\D', '', normalized)
        if 7 <= len(digits_only) <= 15:
            return normalized
    return ''


def extract_name_from_message(text, state):
    lowered = (text or '').lower().strip()
    if not lowered:
        return ''
    if '_' in lowered:
        return ''
    if lowered in NON_NAME_VALUES:
        return ''
    choice_tokens = set()
    for step in CHAT_STEPS:
        for key, label in step.get('quick_replies', []):
            choice_tokens.add((key or '').lower().strip())
            choice_tokens.add((label or '').lower().strip())
    if lowered in choice_tokens:
        return ''
    if is_greeting_text(text):
        return ''
    candidate = extract_name(text)
    if re.search(r'(?:my name is|i am|i\'m|this is)', lowered):
        return candidate

    sanitized = re.sub(r'[^a-zA-Z\s\-\']', ' ', text).strip()
    words = [word for word in sanitized.split() if word]
    if 1 <= len(words) <= 3:
        lowered_words = {word.lower() for word in words}
        if not lowered_words.intersection(NON_NAME_VALUES):
            return ' '.join(words).title()

    first_chunk = text.split(',')[0].strip()
    if first_chunk and not re.search(r'[@0-9]', first_chunk):
        maybe_name = re.sub(r'[^a-zA-Z\s\-\']', '', first_chunk).strip()
        maybe_words = [word for word in maybe_name.split() if word]
        lowered_words = {word.lower() for word in maybe_words}
        if 1 <= len(maybe_words) <= 3 and not lowered_words.intersection(NON_NAME_VALUES):
            return ' '.join(maybe_words).title()
    return ''


def extract_project_type(text):
    lower = (text or '').lower()
    aliases = [
        ('cms', ['starter website', 'website + lead', 'website and lead', 'starter website + lead system', 'website lead system']),
        ('cms', ['lead generation setup', 'lead generation website', 'lead setup']),
        ('ecommerce', ['ecommerce', 'e-commerce', 'woo commerce', 'woocommerce', 'magento', 'shopify', 'store']),
        ('cms', ['cms', 'wordpress', 'wix', 'squarespace', 'webflow', 'website']),
        ('ai', ['ai', 'chatbot', 'assistant automation', 'booking bot', 'business assistant']),
        ('flutter', ['flutter', 'mobile app', 'ios app', 'android app']),
        ('custom', ['custom development', 'custom dev', 'crm', 'erp', 'portal']),
        ('video', ['video', 'video editing', 'animation']),
        ('design', ['design', 'graphic design', 'logo', 'branding']),
        ('social', ['social', 'social promotion', 'social media', 'campaign']),
        ('hosting', ['hosting', 'vps', 'shared hosting', 'dedicated server']),
    ]
    for value, keywords in aliases:
        for keyword in keywords:
            if keyword == 'ai':
                if re.search(r'\bai\b', lower):
                    return value
                continue
            if keyword in lower:
                return value
    return ''


def extract_expected_benefit(text):
    lower = (text or '').lower()
    aliases = [
        # Increase sales / revenue
        ('increase_sales', ['increase sales', 'more sales', 'sell more', 'sales', 'revenue', 'profit', 'make money', 'earn', 'income', 'monetize']),
        # Lead generation
        ('lead_generation', ['lead generation', 'more leads', 'get leads', 'leads', 'inquiries', 'contacts', 'customers', 'clients', 'potential customers']),
        # Online presence / branding
        ('brand_awareness', ['website', 'site', 'online presence', 'presence', 'brand awareness', 'brand', 'visibility', 'showcase', 'portfolio', 'display', 'show off', 'professional look']),
        # Automation / efficiency
        ('automation', ['automation', 'automate', 'systemize', 'efficiency', 'save time', 'streamline', 'faster', 'easier', 'less work', 'reduce manual']),
        # Customer support
        ('better_support', ['support', 'customer support', 'better support', 'help customers', 'answer questions', 'service', 'customer service', '24/7', 'chat support']),
        # Credibility / trust
        ('credibility', ['credibility', 'trust', 'professional', 'legitimate', 'serious', 'trustworthy', 'reliable', 'reputation']),
    ]
    for value, keywords in aliases:
        if any(keyword in lower for keyword in keywords):
            return value
    return ''


def extract_business_ready(text):
    lower = (text or '').lower().strip()
    if any(token in lower for token in ['planning', 'plan to start', 'starting', 'not yet', 'soon']):
        return 'planning'
    if any(token in lower for token in ['yes', 'running', 'already running', 'have business']):
        return 'yes'
    if any(token in lower for token in ['no', "don't", 'not running']):
        return 'no'
    return ''


def extract_customer_source(text):
    lower = (text or '').lower()
    if 'social' in lower:
        return 'social_media'
    if any(token in lower for token in ['word of mouth', 'referral', 'friends']):
        return 'word_of_mouth'
    if any(token in lower for token in ['ads', 'advert', 'google ads', 'facebook ads']):
        return 'ads'
    if any(token in lower for token in ['not started', 'none yet', 'no customers']):
        return 'not_started'
    return ''


def extract_service_plan(text, state):
    lower = (text or '').lower()
    if re.fullmatch(r'\d+', lower.strip()):
        return ''

    aliases = [
        ('1-Page Website (WordPress)', ['1-page website (wordpress)', 'wordpress 1-page', 'wordpress 1 page']),
        ('5-Page Website (WordPress)', ['5-page website (wordpress)', 'wordpress 5-page', 'wordpress 5 page']),
        ('1-Page Website (Wix)', ['1-page website (wix)', 'wix 1-page', 'wix 1 page']),
        ('5-Page Website (Wix)', ['5-page website (wix)', 'wix 5-page', 'wix 5 page']),
        ('1-Page Website (Squarespace)', ['1-page website (squarespace)', 'squarespace 1-page', 'squarespace 1 page']),
        ('5-Page Website (Squarespace)', ['5-page website (squarespace)', 'squarespace 5-page', 'squarespace 5 page']),
        ('1-Page Website (Webflow)', ['1-page website (webflow)', 'webflow 1-page', 'webflow 1 page']),
        ('5-Page Website (Webflow)', ['5-page website (webflow)', 'webflow 5-page', 'webflow 5 page']),
        ('WooCommerce Basic Store', ['woocommerce basic store', 'woocommerce basic', 'woocommerce']),
        ('Magento 2 Basic', ['magento 2 basic', 'magento basic', 'magento']),
        ('VPS Plus', ['vps plus']),
        ('VPS', ['vps']),
        ('Shared Hosting Basic', ['shared hosting basic']),
        ('Shared Hosting E-commerce', ['shared hosting e-commerce', 'shared hosting ecommerce']),
        ('Shared Hosting Plus', ['shared hosting plus']),
        ('Dedicated Basic', ['dedicated basic']),
        ('Dedicated Plus', ['dedicated plus']),
        ('Dedicated Pro', ['dedicated pro']),
        ('Dedicated Advance', ['dedicated advance']),
        ('AI Booking Assistant', ['ai booking assistant', 'booking assistant']),
        ('AI Business Assistant', ['ai business assistant', 'business assistant']),
        ('AI Chat Assistant', ['ai chat assistant', 'chat assistant']),
        ('Corporate App (Android & iOS)', ['corporate app (android & ios)', 'corporate app']),
        ('Booking App (Android & iOS)', ['booking app (android & ios)', 'booking app']),
        ('CRM System', ['crm system', 'custom crm', 'crm']),
        ('ERP System', ['erp system', 'custom erp', 'erp']),
        ('Video Editing (30 sec)', ['video editing (30 sec)', '30 sec video', '30 second video']),
        ('Animation Video', ['animation video', 'animation']),
        ('AI Logo Design', ['ai logo design', 'ai logo']),
        ('Basic Logo Design', ['basic logo design', 'basic logo']),
        ('Custom Logo Design', ['custom logo design', 'custom logo']),
        ('Campaign Setup', ['campaign setup']),
        ('Basic Monthly', ['basic monthly']),
        ('Standard Monthly', ['standard monthly']),
        ('Advanced Monthly', ['advanced monthly']),
    ]
    for value, keywords in aliases:
        if any(keyword in lower for keyword in keywords):
            return value

    project_type = state.get('collected', {}).get('project_type', '')
    generic_map = {
        'ecommerce': ['woocommerce', 'magento'],
        'cms': ['wordpress', 'wix', 'squarespace', 'webflow'],
        'hosting': ['shared', 'vps', 'dedicated'],
    }
    for keyword in generic_map.get(project_type, []):
        if keyword in lower:
            if keyword == 'vps':
                return 'VPS'
            if keyword == 'shared':
                return 'Shared Hosting Basic'
            if keyword == 'dedicated':
                return 'Dedicated Basic'
            if keyword == 'woocommerce':
                return 'WooCommerce Basic Store'
            if keyword == 'magento':
                return 'Magento 2 Basic'
            if keyword == 'wordpress':
                return '1-Page Website (WordPress)'
            if keyword == 'wix':
                return '1-Page Website (Wix)'
            if keyword == 'squarespace':
                return '1-Page Website (Squarespace)'
            if keyword == 'webflow':
                return '1-Page Website (Webflow)'
    return ''


def extract_selected_feature(text):
    lower = (text or '').lower()
    aliases = [
        ('none', ['no add-on', 'no addon', 'none', 'no add on', 'skip', 'nothing', 'no thanks', 'no extra']),
        ('seo_pro', ['seo pro', 'seo', 'search engine', 'google ranking', 'search optimization']),
        ('booking_system', ['booking system', 'booking', 'appointment', 'schedule', 'reservation']),
        ('speed_optimization', ['speed optimization', 'speed optimisation', 'speed', 'fast loading', 'performance', 'speed boost']),
        ('security', ['security', 'secure site', 'ssl', 'protection', 'security package']),
        ('analytics', ['analytics', 'tracking', 'google analytics', 'stats', 'statistics']),
        ('social_integration', ['social media', 'social links', 'facebook', 'instagram', 'social integration']),
    ]
    for value, keywords in aliases:
        if any(keyword in lower for keyword in keywords):
            return value
    return ''


def extract_content_delivery(text):
    lower = (text or '').lower()
    # Client provides
    if any(phrase in lower for phrase in ['client provides', 'i provide', 'i will provide', 'we have content', 'client will provide', 'i have', 'already have', 'got content', 'have everything', 'i have content', 'my content']):
        return 'client_provides'
    # We create
    if any(phrase in lower for phrase in ['we create', 'you create', 'need content creation', 'create content', 'make content', 'write content', 'need help with content', 'no content', "don't have content", 'dont have content']):
        return 'we_create'
    # Mixed
    if any(phrase in lower for phrase in ['mixed', 'both', 'some', 'partial', 'half', 'combination', 'little bit']):
        return 'mixed'
    # Not sure
    if any(phrase in lower for phrase in ['not sure', 'unsure', 'dont know', "don't know", 'maybe', 'depends']):
        return 'not_sure'
        return 'we_create'
    if 'mixed' in lower:
        return 'mixed'
    return ''


def extract_budget_range(text):
    lower = (text or '').lower()
    
    # Natural language understanding for budget
    # Very low budget indicators
    if any(phrase in lower for phrase in ['very tight', 'very limited', 'super low', 'minimal', 'starter', 'basic', 'under 150', 'below 150', 'less than 150', 'under $150', 'below $150']):
        return 'very_low'
    
    # Low budget indicators  
    if any(phrase in lower for phrase in ['tight', 'limited', 'cheap', 'affordable', 'budget friendly', 'low budget', 'small budget', 'under 300', 'below 300', 'less than 300', 'under $300', 'below $300', '150 to 300', '$150 to $300', '150-300', '$150-$300']):
        return 'low'
    
    # Mid budget indicators
    if any(phrase in lower for phrase in ['moderate', 'medium', 'mid range', 'middle', 'reasonable', '300 to 1000', '$300 to $1000', 'between 300 and 1000', '300-1000', '$300-$1000', 'few hundred', 'several hundred']):
        return 'mid'
    
    # High budget indicators
    if any(phrase in lower for phrase in ['good budget', 'decent budget', 'comfortable', '1000 to 3000', '$1000 to $3000', '1000-3000', '$1000-$3000', 'thousand', 'couple thousand']):
        return 'high'
    
    # Premium budget indicators
    if any(phrase in lower for phrase in ['premium', 'no limit', 'unlimited', 'big budget', 'large budget', 'serious budget', 'above 3000', 'over 3000', 'more than 3000', 'above $3000', 'over $3000', 'several thousand', 'multiple thousand']):
        return 'premium'
    
    # Undecided indicators
    if any(phrase in lower for phrase in ['not sure', 'undecided', 'dont know', "don't know", 'no idea', 'unsure', 'depends', 'flexible', 'open', 'tell me']):
        return 'undecided'

    # Try to extract dollar amounts
    budget_context = any(token in lower for token in ['budget', '$', 'usd', 'dollar', 'spend', 'pay', 'cost'])
    amounts = [int(match) for match in re.findall(r'\$?(\d{2,5})', lower)]
    if amounts:
        ceiling = max(amounts)
        if ceiling < 150:
            return 'very_low'
        if ceiling < 300:
            return 'low'
        if ceiling <= 1000:
            return 'mid'
        if ceiling <= 3000:
            return 'high'
        return 'premium'
    return ''


def extract_timeline(text):
    lower = (text or '').lower()
    
    # Urgent indicators
    if any(phrase in lower for phrase in ['urgent', 'asap', 'emergency', 'immediately', 'right now', 'today', 'tomorrow', '1 day', '2 days', 'within 2 days', 'rush', 'critical', 'deadline']):
        return 'urgent'
    
    # Fast indicators
    if any(phrase in lower for phrase in ['fast', 'quick', 'soon', 'this week', '3 days', '4 days', '5 days', 'few days', 'couple days', 'within a week', 'hurry', 'speedy']):
        return 'fast'
    
    # Normal indicators
    if any(phrase in lower for phrase in ['normal', 'standard', 'regular', '7 days', '10 days', 'week', 'two weeks', '1-2 weeks', '1 to 2 weeks', 'typical', 'average']):
        return 'normal'
    
    # Relaxed/flexible indicators (maps to relaxed)
    if any(phrase in lower for phrase in ['slow', 'relaxed', 'flexible', 'no rush', 'no hurry', 'whenever', 'take your time', 'not urgent', 'chill', 'easy', 'leisure', 'month', '2-4 weeks', '3-4 weeks', 'couple weeks', 'few weeks', 'anytime', 'no deadline']):
        return 'relaxed'
    
    return ''


def extract_optional_boolean(field, text):
    lower = (text or '').lower()
    patterns = {
        'is_decision_maker': ['decision maker', 'i decide', 'final approver'],
        'can_pay_deposit': ['deposit', 'advance payment', 'upfront payment'],
        'willing_to_call': ['call', 'phone call', 'quick call'],
    }
    if field == 'is_decision_maker' and any(phrase in lower for phrase in ['i am the decision maker', 'i am decision maker']):
        return True
    if field == 'can_pay_deposit' and any(phrase in lower for phrase in ['can pay deposit', 'ready to pay deposit']):
        return True
    if field == 'willing_to_call' and any(phrase in lower for phrase in ['available for a call', 'open for a call', 'ready for a call']):
        return True

    if not any(marker in lower for marker in patterns[field]):
        return None
    if any(token in lower for token in [' no ', ' not ', "can't", 'cannot']):
        return False
    if any(token in lower for token in [' yes ', ' can ', ' ready ', ' available ', ' am ']):
        return True
    return None


def extract_fields_from_message(text, state):
    extracted = {}
    step = current_step(state)
    missing_required = missing_fields(state, MANDATORY_FIELDS)

    # Strict step lock with one approved convenience rule:
    # while in contact capture, allow one message to include name/phone/email together.
    if step and step['field'] in {'name', 'phone', 'email'}:
        if 'name' in missing_required:
            name = extract_name_from_message(text, state)
            if name:
                extracted['name'] = name
        if 'phone' in missing_required:
            phone = extract_phone(text)
            if phone:
                extracted['phone'] = phone
        if 'email' in missing_required:
            email = extract_email(text)
            if email:
                extracted['email'] = email
        # Continue to opportunistic parsing so one natural sentence can fill multiple fields.

    if step:
        field = step['field']
        if field == 'project_type':
            value = extract_project_type(text)
            if value:
                extracted[field] = value
        elif field == 'expected_benefit':
            value = extract_expected_benefit(text)
            if value:
                extracted[field] = value
        elif field == 'service_plan':
            value = extract_service_plan(text, state)
            if value:
                extracted[field] = value
        elif field == 'selected_features':
            value = extract_selected_feature(text)
            if value:
                extracted[field] = value
        elif field == 'content_delivery':
            value = extract_content_delivery(text)
            if value:
                extracted[field] = value
        elif field == 'budget_range':
            value = extract_budget_range(text)
            if value:
                extracted[field] = value
        elif field == 'timeline':
            value = extract_timeline(text)
            if value:
                extracted[field] = value

    pending_risk_field = pending_risk_check_field(state, analyze_process_state(state.get('collected', {})))
    if pending_risk_field and pending_risk_field not in state.get('answered_fields', []):
        value = extract_optional_boolean(pending_risk_field, text)
        if value is not None:
            extracted[pending_risk_field] = value

    # Opportunistic extraction: never waste useful user input.
    if 'name' in missing_required and 'name' not in extracted:
        name = extract_name_from_message(text, state)
        if name:
            extracted['name'] = name
    if 'phone' in missing_required and 'phone' not in extracted:
        phone = extract_phone(text)
        if phone:
            extracted['phone'] = phone
    if 'email' in missing_required and 'email' not in extracted:
        email = extract_email(text)
        if email:
            extracted['email'] = email
    if 'expected_benefit' in missing_required and 'expected_benefit' not in extracted:
        benefit = extract_expected_benefit(text)
        if benefit:
            extracted['expected_benefit'] = benefit
    if 'budget_range' in missing_required and 'budget_range' not in extracted:
        budget = extract_budget_range(text)
        if budget:
            extracted['budget_range'] = budget
    if 'project_type' in missing_required and 'project_type' not in extracted:
        project = extract_project_type(text)
        if project:
            extracted['project_type'] = project
    if 'contact_preference' in missing_required and wants_human(text):
        extracted['contact_preference'] = 'human'

    return extracted


def goal_to_primary_goal(expected_benefit):
    mapping = {
        'increase_sales': 'online_sales',
        'lead_generation': 'website_presence',
        'brand_awareness': 'website_presence',
        'automation': 'automation',
        'better_support': 'automation',
    }
    return mapping.get(expected_benefit, 'website_presence')


def auto_service_plan(project_type, expected_benefit):
    if project_type == 'cms':
        if expected_benefit == 'brand_awareness':
            return '1-Page Website (WordPress)'
        return '5-Page Website (WordPress)'
    if project_type == 'ecommerce':
        return 'WooCommerce Basic Store'
    if project_type == 'ai':
        if expected_benefit == 'better_support':
            return 'AI Chat Assistant'
        return 'AI Business Assistant'
    if project_type == 'custom':
        return 'CRM System'
    return ''


def sync_derived_fields(state):
    collected = state.get('collected', {})
    expected_benefit = collected.get('expected_benefit', '')
    project_type = collected.get('project_type', '')
    if expected_benefit:
        collected['primary_goal'] = goal_to_primary_goal(expected_benefit)
    if project_type:
        plan = auto_service_plan(project_type, expected_benefit)
        if plan:
            collected['service_plan'] = plan


def save_extracted_fields(state, extracted):
    saved_fields = []
    for field, value in extracted.items():
        if field in OPTIONAL_FIELDS:
            state['collected'][field] = value
            mark_field_answered(state, field)
            saved_fields.append(field)
            continue
        normalized = normalize_choice_value(FIELD_CONFIG.get(field), value) if FIELD_CONFIG.get(field) else value
        step_cfg = FIELD_CONFIG[field]
        if field == 'project_type':
            step_cfg = dict(step_cfg)
            step_cfg['_state_collected'] = state.get('collected', {})
        if validate_step(step_cfg, normalized):
            state['collected'][field] = parse_value(field, normalized)
            mark_field_answered(state, field)
            saved_fields.append(field)
    sync_derived_fields(state)
    sync_step_index(state)
    return saved_fields


def summarize_saved_fields(saved_fields, lang):
    mandatory_saved = [field for field in saved_fields if field in MANDATORY_FIELDS]
    optional_saved = [field for field in saved_fields if field in OPTIONAL_FIELDS]

    contact_saved = set(['name', 'phone', 'email']).issubset(set(mandatory_saved))
    understanding_saved = set(['project_type', 'expected_benefit']).issubset(set(mandatory_saved))
    mapping_saved = set(['selected_features', 'content_delivery']).issubset(set(mandatory_saved))
    budget_saved = 'budget_range' in mandatory_saved
    timeline_saved = 'timeline' in mandatory_saved

    if contact_saved:
        return t(lang, 'Saved: contact details.', 'Opgeslagen: contactgegevens.')
    if understanding_saved:
        return t(lang, 'Saved: project understanding.', 'Opgeslagen: projectcontext.')
    if mapping_saved:
        return t(lang, 'Saved: service mapping.', 'Opgeslagen: servicemapping.')
    if budget_saved:
        return t(lang, 'Saved: budget range.', 'Opgeslagen: budgetbereik.')
    if timeline_saved:
        return t(lang, 'Saved: timeline.', 'Opgeslagen: planning.')

    parts = []
    if mandatory_saved:
        parts.append(t(lang, f'Saved: {format_field_list(mandatory_saved)}.', f'Opgeslagen: {format_field_list(mandatory_saved)}.'))
    if optional_saved:
        parts.append(t(lang, f'Optional details saved: {format_field_list(optional_saved)}.', f'Optionele details opgeslagen: {format_field_list(optional_saved)}.'))
    return ' '.join(parts) if parts else t(lang, 'Noted.', 'Genoteerd.')


def greeting_message(lang, seen_intro=False):
    return translated(
        lang,
        'Hi again. Let us continue your project details.' if seen_intro else 'Hi, this is Divi Hosting. I will guide your project details step by step.',
        'Hallo opnieuw. Laten we uw projectgegevens vervolgen.' if seen_intro else 'Hallo, dit is Divi Hosting. Ik begeleid uw projectgegevens stap voor stap.',
        'Hola de nuevo. Cuentame que necesitas.' if seen_intro else 'Hola, esto es Divi Hosting. Como puedo ayudarte?',
    )
def is_greeting_text(text):
    lower = (text or '').lower().strip()
    compact = re.sub(r'[^a-z]', '', lower)
    if not compact:
        return False
    return bool(re.fullmatch(r'(h+i+|h+e+y+|h+e+l+o+|h+a+l+o+|h+o+l+a+)', compact))


def likely_nonsense(text):
    lower = (text or '').lower().strip()
    valid_choice_tokens = set(NON_NAME_VALUES)
    for step in CHAT_STEPS:
        for key, label in step.get('quick_replies', []):
            valid_choice_tokens.add((key or '').lower().strip())
            valid_choice_tokens.add((label or '').lower().strip())
    if lower in valid_choice_tokens:
        return False

    compact = re.sub(r'\s+', '', lower)
    if not lower:
        return True
    if len(compact) >= 5 and len(set(compact)) == 1:
        return True
    if re.fullmatch(r'[\W_]+', lower):
        return True
    if re.fullmatch(r'[a-z]{1,4}', compact):
        return True
    bad_patterns = [
        'how long is a chinese',
        'asdf',
        'qwerty',
        'zxcv',
        'lorem ipsum',
    ]
    return any(p in lower for p in bad_patterns)


def is_smalltalk_or_offtopic(text):
    lower = (text or '').lower().strip()
    markers = {
        'ok', 'okay', 'cool', 'nice', 'hmm', 'hmmm', 'lol', 'thanks', 'thank you',
        'good', 'fine', 'great', 'sure', 'yep', 'bro', 'friend',
    }
    return lower in markers


def normalize_choice_value(step, value):
    v = normalize_input(value)
    if not step:
        return v

    field = step.get('field')
    lower = v.lower()

    if field in ('is_decision_maker', 'can_pay_deposit', 'willing_to_call'):
        if lower in {'yes', 'y'}:
            return 'yes'
        if lower in {'no', 'n'}:
            return 'no'
        if lower in {'skip', 'later', 'not now'}:
            return 'skip'

    for key, label in step.get('quick_replies', []):
        if lower == key.lower() or lower == str(label).lower():
            return key

    aliases = {
        'project_type': {
            'starter website + lead system': 'cms',
            'website + lead capture': 'cms',
            'business website + lead system': 'cms',
            'lead generation setup': 'cms',
            'online store setup': 'ecommerce',
            'ai assistant setup': 'ai',
            'custom business system': 'custom',
            'video editing': 'video',
            'graphic design': 'design',
            'social promotion': 'social',
            'ai services': 'ai',
            'flutter apps': 'flutter',
            'custom development': 'custom',
            'ecommerce': 'ecommerce',
            'hosting': 'hosting',
            'cms': 'cms',
        },
        'business_ready': {
            'yes': 'yes',
            'no': 'no',
            'planning to start': 'planning',
            'planning': 'planning',
        },
        'customer_source': {
            'social media': 'social_media',
            'word of mouth': 'word_of_mouth',
            'ads': 'ads',
            'not started yet': 'not_started',
            'not started': 'not_started',
        },
        'budget_range': {
            'under $150': 'very_low',
            'under 150': 'very_low',
            'below 150': 'very_low',
            '$150 - $300': 'low',
            '150 to 300': 'low',
            '$150-$300': 'low',
            'below $300': 'low',
            'below 300': 'low',
            '$300 - $1000': 'mid',
            '$300 to $1000': 'mid',
            '300 to 1000': 'mid',
            '$1000 - $3000': 'high',
            '1000 to 3000': 'high',
            'above $1000': 'high',
            'above $3000': 'premium',
            'above 3000': 'premium',
            'not sure yet': 'undecided',
            'flexible / no rush (2-4 weeks)': 'relaxed',
            'normal (1-2 weeks)': 'normal',
            'fast (3-5 days)': 'fast',
            'urgent (1-2 days) +$50': 'urgent',
        },
        'contact_preference': {
            'continue with ai': 'ai',
            'talk to human': 'human',
            'ai chat': 'ai',
            'human support': 'human',
        },
        'content_delivery': {
            'client provides': 'client_provides',
            'i will provide': 'client_provides',
            'we create': 'we_create',
            'you create (+20%)': 'we_create',
            'mixed': 'mixed',
            'some of both': 'mixed',
            'not sure yet': 'not_sure',
        },
        'timeline': {
            'flexible / no rush (2-4 weeks)': 'relaxed',
            'normal (1-2 weeks)': 'normal',
            'fast (3-5 days)': 'fast',
            'urgent (1-2 days) +$50': 'urgent',
        },
    }

    mapped = aliases.get(field, {}).get(lower)
    return mapped if mapped else v


def asks_services(text):
    lower = (text or '').lower()
    markers = ['service', 'services', 'what do you do', 'help me', 'diensten', 'service list', 'packages', 'price list']
    return any(marker in lower for marker in markers)


def asks_pricing(text):
    lower = (text or '').lower()
    # Exclude "revise" commands that happen to contain "quote"
    if 'revise' in lower or 'edit' in lower or 'change' in lower:
        return False
    markers = ['price', 'pricing', 'cost', 'how much', 'prijs', 'kosten', 'offerte']
    return any(marker in lower for marker in markers)


def rough_range_for_divi_service(project_type):
    ranges = {
        'cms': '$149 - $399',
        'ecommerce': '$450 - $900',
        'ai': '$125 setup + monthly plans',
        'flutter': '$400 - $600',
        'custom': '$15/hour or fixed quote',
        'video': '$75 - $150',
        'design': '$30 - $125',
        'social': '$75 setup + monthly plans',
        'hosting': '$5 - $250/month',
    }
    return ranges.get(project_type, '$149 - custom quote')


def ai_micro_response(step, lang, state, text):
    field = step['field'] if step else ''
    name = name_from_state(state)
    if field == 'name':
        cleaned_name = extract_name(text)
        return t(lang, f'Great, {cleaned_name}.', f'Prima, {cleaned_name}.')
    if field == 'phone':
        return t(lang, 'Phone saved.', 'Telefoon opgeslagen.')
    if field == 'location':
        return t(lang, 'Location noted.', 'Locatie genoteerd.')
    if field == 'email':
        return t(lang, 'Email saved.', 'E-mail opgeslagen.')
    if field == 'project_type':
        return t(lang, 'Great choice. I will prepare your plan accordingly.', 'Prima keuze. Ik bereid uw plan hierop voor.')
    if field == 'expected_benefit':
        return t(lang, 'Goal captured.', 'Doel vastgelegd.')
    if field == 'business_ready':
        return t(lang, 'Business stage noted.', 'Bedrijfsfase genoteerd.')
    if field == 'customer_source':
        return t(lang, 'Customer source noted.', 'Klantenbron genoteerd.')
    if field == 'budget_range':
        return t(lang, 'Budget range noted.', 'Budgetbereik genoteerd.', 'Rango de presupuesto registrado.')
    if field == 'content_delivery':
        return t(lang, 'Content responsibility noted.', 'Contentverantwoordelijkheid genoteerd.', 'Responsabilidad de contenido registrada.')
    if field == 'timeline':
        return t(lang, 'Timeline noted.', 'Tijdlijn genoteerd.', 'Plazo registrado.')
    if name:
        return t(lang, f'Thanks, {name}.', f'Dank je, {name}.', f'Gracias, {name}.')
    return t(lang, 'Got it.', 'Begrepen.', 'Entendido.')


@require_GET
def assistant_ai_plan_api(request):
    plan = {
        'recommended': {
            'conversation_model': 'Llama 3.1 8B Instruct (fast, cost-efficient)',
            'fallback_model': 'Mistral 7B Instruct (robust fallback)',
            'embedding_model': 'bge-small-en-v1.5 or multilingual-e5-base',
            'guardrail_model': 'distilbert-base-uncased (intent + toxicity filter)',
        },
        'transformer_stack': [
            'Intent classifier -> Response policy -> LLM response -> Rule validator -> Final output',
            'RAG only for pricing/policies from your approved knowledge base',
            'Always enforce mandatory lead-capture steps before free-form mode',
        ],
        'deployment': {
            'phase_1': 'Rule-first chatbot + lightweight LLM for natural phrasing',
            'phase_2': 'Fine-tune intent model using your chat transcripts',
            'phase_3': 'Add multilingual response calibration and A/B evaluation',
        },
    }
    return JsonResponse(plan)


def wants_human(text):
    lower = (text or '').lower()
    markers = [
        'human',
        'real person',
        'agent',
        'staff',
        'someone from team',
        'mens',
        'persoon',
    ]
    return any(marker in lower for marker in markers)


def requests_crm_or_erp(text):
    lower = (text or '').lower()
    markers = [
        'crm',
        'erp',
        'custom system',
        'business system',
        'automation system',
    ]
    return any(marker in lower for marker in markers)


def finish_chat_lead(request, state):
    completed_lead_id = state.get('completed_lead_id')
    if completed_lead_id:
        lead = Lead.objects.filter(id=completed_lead_id).first()
        if lead:
            return lead, {
                'score': lead.lead_score,
                'seriousness_level': lead.seriousness_level,
                'next_action': lead.next_action,
                'can_move_to_intake': lead.is_serious,
                'is_serious': lead.is_serious,
                'reason': lead.disqualification_reason,
            }

    collected = state.get('collected', {})
    first_message = state.get('first_user_message') or ''
    detected_source, campaign, detected_by = detect_source(request)
    source = state.get('source_override') or detected_source
    source_detected_by = 'manual_override' if state.get('source_override') else detected_by

    # ==========================================================================
    # SMART INFERENCE: Auto-assume qualification factors from user behavior
    # ==========================================================================
    phone = collected.get('phone', '')
    budget = collected.get('budget_range', 'undecided') or 'undecided'
    timeline = collected.get('timeline', 'normal') or 'normal'
    content_delivery = collected.get('content_delivery', '')
    answered_fields = state.get('answered_fields', [])
    
    # 1. Has phone = likely decision maker (they're the contact person)
    inferred_decision_maker = bool(phone)
    
    # 2. Completed 5+ fields = engaged, willing to proceed
    inferred_willing = len(answered_fields) >= 5
    
    # 3. Budget mid or higher = business ready, can commit
    inferred_business_ready = budget in {'mid', 'high', 'premium'}
    
    # 4. Budget high/premium = can pay deposit
    inferred_can_pay = budget in {'high', 'premium'}
    
    # 5. Content delivery specified = assets ready
    inferred_assets_ready = content_delivery in {'client_provides', 'mixed'}
    
    # Combine explicit values with inferred defaults
    business_ready_flag = collected.get('business_ready') in {'yes', True} or inferred_business_ready
    is_decision_maker = collected.get('is_decision_maker', False) or inferred_decision_maker
    willing_to_call = collected.get('willing_to_call', False) or inferred_willing
    can_pay_deposit = collected.get('can_pay_deposit', False) or inferred_can_pay
    assets_ready = collected.get('assets_ready', False) or inferred_assets_ready

    qualification = evaluate_lead(
        phone=phone,
        project_type=collected.get('project_type', 'cms'),
        timeline=timeline,
        budget_range=budget,
        is_decision_maker=is_decision_maker,
        business_ready=business_ready_flag,
        willing_to_call=willing_to_call,
        can_pay_deposit=can_pay_deposit,
        assets_ready=assets_ready,
        current_presence_link=collected.get('current_presence_link', ''),
    )

    mapped_project_type = collected.get('project_type', 'cms')
    if mapped_project_type not in {'cms', 'ecommerce', 'ai', 'custom'}:
        mapped_project_type = 'custom'

    recommended, reason = recommend_service(
        mapped_project_type,
        collected.get('primary_goal', 'website_presence'),
        business_ready_flag,
    )

    stage = 'new'
    needs_human = collected.get('contact_preference') == 'human'
    if needs_human:
        stage = 'human_handoff'

    rough_price = rough_range_for_divi_service(collected.get('project_type', 'cms')) if qualification['is_serious'] else ''
    disq = reason if reason else qualification.get('reason', '')

    base_quote_lookup = {
        'cms': 149,
        'ecommerce': 450,
        'ai': 125,
        'flutter': 400,
        'custom': 750,
        'video': 75,
        'design': 60,
        'social': 75,
        'hosting': 5,
    }
    raw_project_type = collected.get('project_type', 'cms')
    base_price = float(base_quote_lookup.get(raw_project_type, 149))
    multiplier_lookup = {'normal': 1.0, 'fast': 1.2, 'urgent': 1.5}
    timeline = collected.get('timeline', 'normal')
    multiplier = multiplier_lookup.get(timeline, 1.0)
    quote_total = round(base_price * multiplier, 2)

    selected_features = collected.get('selected_features', 'none')
    if selected_features and selected_features != 'none':
        selected_features = [selected_features]
    else:
        selected_features = []

    _analyzer = analyze_process_state(collected)
    _processor = processor_snapshot(state, _analyzer)

    lead = Lead.objects.create(
        name=collected.get('name', ''),
        location=collected.get('location', ''),
        email=collected.get('email', ''),
        phone=collected.get('phone', ''),
        first_message=first_message,
        first_message_summary=summarize_first_message(first_message),
        business_name=collected.get('business_name', ''),
        current_presence_link=collected.get('current_presence_link', ''),
        client_need=collected.get('client_need', 'website_presence'),
        client_need_details=collected.get('client_need_details', ''),
        expected_benefit=collected.get('expected_benefit', 'increase_sales'),
        expected_benefit_details=collected.get('expected_benefit_details', ''),
        willing_to_call=collected.get('willing_to_call', False),
        can_pay_deposit=collected.get('can_pay_deposit', False),
        assets_ready=collected.get('assets_ready', False),
        logo_ready=collected.get('logo_ready', False),
        content_ready=collected.get('content_ready', False),
        images_ready=collected.get('images_ready', False),
        source=source,
        source_campaign=campaign,
        source_detected_by=source_detected_by,
        project_type=mapped_project_type,
        primary_goal=collected.get('primary_goal', 'website_presence'),
        budget_range=collected.get('budget_range', 'undecided'),
        is_decision_maker=collected.get('is_decision_maker', False),
        business_ready=business_ready_flag,
        timeline=collected.get('timeline', 'normal') or 'normal',
        contact_preference=collected.get('contact_preference', 'ai'),
        stage=stage,
        lead_score=qualification['score'],
        seriousness_level=qualification['seriousness_level'],
        is_serious=qualification['is_serious'],
        needs_human=needs_human,
        recommended_service=recommended,
        disqualification_reason=disq,
        rough_price=rough_price,
        service_specific_data={
            'service_type': raw_project_type,
            'service_plan': collected.get('service_plan', ''),
        },
        selected_features=selected_features,
        content_delivery=collected.get('content_delivery', ''),
        quote_price=quote_total,
        quote_breakdown={
            'service_type': raw_project_type,
            'service_plan': collected.get('service_plan', ''),
            'base_price': base_price,
            'timeline': timeline,
            'multiplier': multiplier,
            'selected_features': selected_features,
            'total': quote_total,
        },
        quote_date=timezone.now(),
        quote_status='sent',
        current_workflow_step='intake',
        next_action='LEAD_CAPTURED -> INTAKE_PENDING',
        processor_phase=_processor['phase'],
        readiness_percent=_analyzer['readiness_percent'],
        risk_flags=_analyzer['risk_flags'],
        contact_block_complete=_processor['contact_block'] == 'complete',
        service_block_complete=_processor['service_block'] == 'complete',
        delivery_block_complete=_processor['delivery_block'] == 'complete',
        qualified_for_handoff=_processor['phase'] == 'QUALIFIED_FOR_HANDOFF',
        risk_check_required=_processor.get('risk_check_required', False),
        service_plan=collected.get('service_plan', ''),
    )

    request.session['lead_id'] = lead.id
    request.session['rough_price'] = rough_price
    state['completed_lead_id'] = lead.id
    schedule_default_followups(lead)
    if first_message:
        log_communication(
            lead=lead,
            channel='whatsapp',
            direction='inbound',
            message_type='lead_message',
            content=first_message,
        )
    return lead, qualification


def build_process_labels(lead):
    process_map = {
        'sales': 'LEAD_CAPTURE',
        'intake': 'INTAKE_PENDING',
        'pricing': 'QUOTE_PENDING',
        'production': 'PRODUCTION_PENDING',
        'invoice': 'INVOICE_PENDING',
        'delivery': 'DELIVERY_REVIEW',
        'support': 'SUPPORT_ACTIVE',
    }
    return {
        'lead_label': 'LEAD_CAPTURED',
        'process_label': process_map.get(lead.current_workflow_step, 'PROCESS_PENDING'),
    }


def labels_for_state(state):
    lead_id = state.get('completed_lead_id')
    if lead_id:
        lead = Lead.objects.filter(id=lead_id).first()
        if lead:
            return build_process_labels(lead)
    return {
        'lead_label': 'Waiting',
        'process_label': 'Waiting',
    }


HIGH_RISK_FLAGS = {'BUDGET_UNCLEAR', 'DECISION_MAKER_UNCLEAR', 'DEPOSIT_RISK'}


def pending_risk_check_field(state, analyzer):
    # Consultant mode: do not block users with internal qualification questions.
    return None


def analyze_process_state(collected):
    mandatory = [
        'name',
        'email',
        'phone',
        'project_type',
        'expected_benefit',
        'selected_features',
        'content_delivery',
        'budget_range',
        'timeline',
    ]
    completed = 0
    missing = []
    for field in mandatory:
        val = collected.get(field)
        if val in (None, '', []):
            missing.append(field)
        else:
            completed += 1

    readiness = int((completed / len(mandatory)) * 100)
    risk_flags = []
    if collected.get('timeline') == 'urgent':
        risk_flags.append('TIMELINE_PRESSURE')

    if readiness < 70:
        next_label = 'DISCOVERY_IN_PROGRESS'
    elif risk_flags:
        next_label = 'CONSULTATION_READY'
    else:
        next_label = 'PLAN_READY'

    return {
        'readiness_percent': readiness,
        'missing_fields': missing,
        'risk_flags': risk_flags,
        'next_label': next_label,
    }


def processor_snapshot(state, analyzer):
    collected = state.get('collected', {})
    contact_done = set(['name', 'phone', 'email']).issubset({k for k, v in collected.items() if v not in ('', None, [])})
    understanding_done = set(['project_type', 'expected_benefit']).issubset({k for k, v in collected.items() if v not in ('', None, [])})
    mapping_done = set(['selected_features', 'content_delivery']).issubset({k for k, v in collected.items() if v not in ('', None, [])})
    budget_done = set(['budget_range', 'timeline']).issubset({k for k, v in collected.items() if v not in ('', None, [])})

    risk_check_required = False
    if not contact_done:
        phase = 'CONTACT_CAPTURE'
    elif not understanding_done:
        phase = 'PROJECT_UNDERSTANDING'
    elif not mapping_done:
        phase = 'SERVICE_MAPPING'
    elif not budget_done:
        phase = 'BUDGET_TIMELINE_VALIDATION'
    else:
        phase = 'QUALIFIED_FOR_HANDOFF'

    return {
        'phase': phase,
        'contact_block': 'complete' if contact_done else 'pending',
        'service_block': 'complete' if mapping_done else 'pending',
        'delivery_block': 'complete' if budget_done else 'pending',
        'next_action': analyzer.get('next_label', 'WAITING'),
        'risk_check_required': risk_check_required,
    }


def enrich_response(state, payload):
    analyzer = payload.get('analyzer') or analyze_process_state(state.get('collected', {}))
    payload['analyzer'] = analyzer
    payload['processor'] = payload.get('processor') or processor_snapshot(state, analyzer)
    payload['labels'] = payload.get('labels') or labels_for_state(state)
    payload['progress'] = payload.get('progress') or progress_snapshot(state)
    if not payload.get('done'):
        quick = payload.get('quick_replies') or []
        payload['quick_replies'] = quick if quick else starter_quick_replies(state.get('lang', 'en'))
    return payload


def practical_next_steps(analyzer):
    risks = analyzer.get('risk_flags', [])
    if not risks:
        return 'Practical next: intake confirmation, timeline lock, then invoice draft.'

    actions = []
    if 'SERVICE_PLAN_MISMATCH' in risks:
        actions.append('align service category with chosen plan')
    if 'BUDGET_UNCLEAR' in risks:
        actions.append('confirm budget range before final quote')
    if 'DEPOSIT_RISK' in risks:
        actions.append('confirm starter deposit plan')
    if 'DECISION_MAKER_UNCLEAR' in risks:
        actions.append('confirm approval decision maker')
    if 'TIMELINE_PRESSURE' in risks:
        actions.append('review urgency surcharge impact')
    return 'Practical next: ' + '; '.join(actions) + '.'


@require_POST
def assistant_message_api(request):
    text = normalize_input(request.POST.get('message', ''))

    state = ensure_assistant_state(request.session.get('assistant_state', initial_assistant_state()))

    if text:
        detected_lang = detect_language(text)
        if detected_lang:
            state['lang'] = detected_lang
    lang = state.get('lang', 'en')

    if not state.get('first_user_message') and text:
        state['first_user_message'] = text

    step = current_step(state) or CHAT_STEPS[0]
    if not text:
        answered_any = any(is_field_complete(state, field) for field in MANDATORY_FIELDS)
        first_interaction = not state.get('first_user_message') and not answered_any
        if state.get('awaiting_start_confirmation', False):
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(
                    lang,
                    'Hi, this is Divi Hosting. We build websites, e-commerce, AI systems, and custom business software. I can guide you from idea to quote.',
                    'Hallo, dit is Divi Hosting. We bouwen websites, e-commerce, AI-systemen en maatwerksoftware. Ik begeleid u van idee tot offerte.',
                    'Hola, esto es Divi Hosting. Construimos sitios web, e-commerce, sistemas AI y software personalizado. Puedo guiarte de idea a cotizacion.',
                ),
                'next_prompt': t(
                    lang,
                    'Would you like to proceed?',
                    'Wilt u doorgaan?',
                    'Quieres continuar?',
                ),
                'quick_replies': [('yes', 'Yes, Proceed'), ('no', 'Not Now')],
                'done': False,
            }))
        resume_message = t(
            lang,
            'Hi, this is Divi Hosting. I will recommend the best path for your goal.' if first_interaction else ('Welcome back. Let us continue where you left off.' if answered_any else 'Let us begin with your details.'),
            'Hallo, dit is Divi Hosting. Ik adviseer het beste pad voor uw doel.' if first_interaction else ('Welkom terug. Laten we doorgaan waar u gebleven was.' if answered_any else 'Laten we beginnen met uw gegevens.'),
            'Hola, esto es Divi Hosting. Recomiendo la mejor ruta para tu objetivo.' if first_interaction else ('Bienvenido de nuevo. Continuemos donde lo dejaste.' if answered_any else 'Comencemos con tus datos.'),
        )
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': resume_message,
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    lower_text = text.lower().strip()
    
    # Handle edit:field commands from ANYWHERE in the flow (not just awaiting_edit_choice)
    if lower_text.startswith('edit:'):
        field = lower_text.split(':', 1)[1]
        if field in MANDATORY_FIELDS:
            state.get('collected', {}).pop(field, None)
            if field in state.get('answered_fields', []):
                state['answered_fields'] = [f for f in state['answered_fields'] if f != field]
            # Clear any special awaiting states
            state['awaiting_edit_choice'] = False
            state['awaiting_confirmation'] = False
            state['awaiting_bulk_contact'] = False
            state['awaiting_post_save_choice'] = False
            sync_step_index(state)
            step = current_step(state) or CHAT_STEPS[0]
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, f'{field_label(field).title()} cleared. Please enter new value.', f'{field_label(field).title()} gewist. Vul een nieuwe waarde in.', f'{field_label(field).title()} eliminado. Introduce un nuevo valor.'),
                'next_prompt': prompt_for_step(step, lang, state),
                'quick_replies': quick_replies_for_state(state),
                'done': False,
            }))
    
    if lower_text in {'start over', 'startover', 'reset', 'restart'}:
        state = initial_assistant_state()
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Starting over. Let us begin again.', 'Opnieuw gestart. Laten we opnieuw beginnen.', 'Reiniciado. Empecemos de nuevo.'),
            'next_prompt': prompt_for_step(current_step(state) or CHAT_STEPS[0], lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if state.get('awaiting_start_confirmation'):
        if requests_crm_or_erp(text):
            state['awaiting_start_confirmation'] = False
            state['awaiting_bulk_contact'] = False
            request.session['assistant_state'] = state
        if lower_text in {'yes', 'proceed', 'start', 'continue'}:
            state['awaiting_start_confirmation'] = False
            state['awaiting_bulk_contact'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(
                    lang,
                    'Great. Please share your full name, email, and phone in one message. You can also mention what you need.',
                    'Top. Deel uw volledige naam, e-mail en telefoon in een bericht. U kunt ook vermelden wat u nodig heeft.',
                    'Perfecto. Comparte tu nombre completo, correo y telefono en un solo mensaje. Tambien puedes decir que necesitas.',
                ),
                'next_prompt': t(
                    lang,
                    'Example: John Doe, john@email.com, +5971234567, need a website',
                    'Voorbeeld: John Doe, john@email.com, +31612345678, ik heb een website nodig',
                    'Ejemplo: John Doe, john@email.com, +5971234567, necesito un sitio web',
                ),
                'quick_replies': [],
                'done': False,
            }))
        if lower_text in {'no', 'not now', 'later'}:
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'No problem. Come back anytime and I will help you.', 'Geen probleem. Kom gerust terug, ik help u dan verder.', 'Sin problema. Vuelve cuando quieras y te ayudo.'),
                'next_prompt': t(lang, 'Tap Reset when you are ready to start.', 'Tik op Reset wanneer u klaar bent om te starten.', 'Pulsa Reset cuando quieras empezar.'),
                'quick_replies': [],
                'done': True,
            }))
        if not requests_crm_or_erp(text):
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'I can guide you quickly from intake to estimate.', 'Ik kan u snel begeleiden van intake tot prijsindicatie.', 'Hola. Puedo guiarte rapido desde la toma de datos hasta la estimacion.'),
                'next_prompt': t(lang, 'Would you like to proceed?', 'Wilt u doorgaan?', 'Quieres continuar?'),
                'quick_replies': [('yes', 'Yes, Proceed'), ('no', 'Not Now')],
                'done': False,
            }))

    if state.get('awaiting_bulk_contact'):
        extracted = {}
        # Only extract fields that are MISSING - don't overwrite already saved valid fields
        missing_contact = missing_fields(state, ['name', 'email', 'phone'])
        
        if 'name' in missing_contact:
            name = extract_name_from_message(text, state)
            if name:
                extracted['name'] = name
        if 'email' in missing_contact:
            email = extract_email(text)
            if email:
                extracted['email'] = email
        if 'phone' in missing_contact:
            phone = extract_phone(text)
            if phone:
                extracted['phone'] = phone

        saved_fields = save_extracted_fields(state, extracted)
        missing_contact = missing_fields(state, ['name', 'email', 'phone'])
        if missing_contact:
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': summarize_saved_fields(saved_fields, lang) if saved_fields else t(lang, 'Thanks. I still need your contact details.', 'Dank u. Ik heb nog uw contactgegevens nodig.', 'Gracias. Aun necesito tus datos de contacto.'),
                'next_prompt': t(lang, f"Please share: {format_field_list(missing_contact)}.", f"Deel alstublieft: {format_field_list(missing_contact)}.", f"Por favor comparte: {format_field_list(missing_contact)}."),
                'quick_replies': [],
                'done': False,
            }))

        state['awaiting_bulk_contact'] = False
        sync_step_index(state)
        next_step = current_step(state)
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Perfect. Contact details saved.', 'Perfect. Contactgegevens opgeslagen.', 'Perfecto. Datos de contacto guardados.'),
            'next_prompt': prompt_for_step(next_step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if state.get('awaiting_budget_resolution'):
        # Budget loop breaker: after MAX_BUDGET_RETRIES force a path
        retry_count = state.get('budget_retry_count', 0)
        
        if lower_text in {'downgrade', 'downgrade_service', 'simpler', 'suggest simpler solution'}:
            state['awaiting_budget_resolution'] = False
            state['budget_retry_count'] = 0  # Reset on resolution
            state['collected']['project_type'] = 'cms'
            state['collected']['service_plan'] = '1-Page Website (WordPress)'
            if 'BUDGET_TOO_LOW' in state.get('risk_flags', []):
                state['risk_flags'].remove('BUDGET_TOO_LOW')
            sync_step_index(state)
            next_step = current_step(state)
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Done. Switched to a simpler solution that fits your budget.', 'Klaar. Omgezet naar een eenvoudigere oplossing die bij uw budget past.', 'Listo. Cambiado a una solucion mas simple para tu presupuesto.'),
                'next_prompt': prompt_for_step(next_step, lang, state),
                'quick_replies': quick_replies_for_state(state),
                'done': False,
            }))
        if lower_text in {'adjust_budget', 'adjust', 'change budget'}:
            retry_count += 1
            state['budget_retry_count'] = retry_count
            
            # Check if exceeded retries
            if retry_count >= MAX_BUDGET_RETRIES:
                state['awaiting_budget_resolution'] = False
                state['budget_retry_count'] = 0
                state['collected']['contact_preference'] = 'human'
                request.session['assistant_state'] = state
                return JsonResponse(enrich_response(state, {
                    'message': t(lang, 'We have tried adjusting budget twice. Connecting you with a team member who can discuss custom options.', 'We hebben het budget twee keer aangepast. Verbinden met een teamlid voor maatwerkopties.', 'Hemos ajustado el presupuesto dos veces. Te conecto con un miembro del equipo.'),
                    'next_prompt': t(lang, 'A teammate will contact you shortly.', 'Een teamlid neemt snel contact op.', 'Un companero te contactara pronto.'),
                    'quick_replies': [],
                    'done': True,
                    'redirect_url': '/human/',
                }))
            
            state['awaiting_budget_resolution'] = False
            state.get('collected', {}).pop('budget_range', None)
            if 'budget_range' in state.get('answered_fields', []):
                state['answered_fields'] = [f for f in state['answered_fields'] if f != 'budget_range']
            sync_step_index(state)
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'OK. Select a different budget range.', 'OK. Selecteer een ander budgetbereik.', 'OK. Selecciona otro rango de presupuesto.'),
                'next_prompt': prompt_for_step(FIELD_CONFIG['budget_range'], lang, state),
                'quick_replies': FIELD_CONFIG['budget_range'].get('quick_replies', []),
                'done': False,
            }))
        if lower_text in {'human', 'talk to human', 'agent'}:
            state['awaiting_budget_resolution'] = False
            state['budget_retry_count'] = 0
            state['collected']['contact_preference'] = 'human'
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Connecting you with a teammate now.', 'U wordt nu verbonden met een teamlid.', 'Conectandote con un companero ahora.'),
                'next_prompt': t(lang, 'A teammate will contact you shortly.', 'Een teamlid neemt snel contact op.', 'Un companero te contactara pronto.'),
                'quick_replies': [],
                'done': True,
                'redirect_url': '/human/',
            }))
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Please select an option to continue.', 'Selecteer een optie om door te gaan.', 'Selecciona una opcion para continuar.'),
            'next_prompt': t(lang, 'Choose: simpler solution, adjust budget, or talk to human.', 'Kies: eenvoudiger, budget aanpassen, of menselijk contact.', 'Elige: solucion simple, ajustar presupuesto, o hablar con humano.'),
            'quick_replies': [
                ('downgrade_service', 'Simpler Solution'),
                ('adjust_budget', 'Adjust Budget'),
                ('human', 'Talk to Human'),
            ],
            'done': False,
        }))

    if state.get('awaiting_csat'):
        lead = Lead.objects.filter(id=state.get('csat_lead_id')).first()
        # Handle typos like 'yess', 'yea', 'yepp'
        if lower_text in {'yes', 'yess', 'yea', 'yeah', 'yep', 'yepp', 'helpful', 'good', 'y'}:
            if lead:
                lead.csat_helpful = True
                lead.save(update_fields=['csat_helpful'])
            state['awaiting_csat'] = False
            state['awaiting_csat_comment'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Thank you. Any quick comment to improve?', 'Dank u. Nog een korte opmerking ter verbetering?', 'Gracias. Alguna nota rapida para mejorar?'),
                'next_prompt': t(lang, 'Optional: type feedback or tap Skip.', 'Optioneel: typ feedback of tik op Overslaan.', 'Opcional: escribe comentarios o pulsa Omitir.'),
                'quick_replies': [('skip', 'Skip')],
                'done': False,
            }))
        if lower_text in {'no', 'not helpful', 'bad'}:
            if lead:
                lead.csat_helpful = False
                lead.save(update_fields=['csat_helpful'])
            state['awaiting_csat'] = False
            state['awaiting_csat_comment'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Thanks for your honesty. How can we improve?', 'Dank voor uw eerlijkheid. Hoe kunnen we verbeteren?', 'Gracias por tu sinceridad. Como podemos mejorar?'),
                'next_prompt': t(lang, 'Optional: type feedback or tap Skip.', 'Optioneel: typ feedback of tik op Overslaan.', 'Opcional: escribe comentarios o pulsa Omitir.'),
                'quick_replies': [('skip', 'Skip')],
                'done': False,
            }))
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Please rate this chat first.', 'Geef eerst een beoordeling voor deze chat.', 'Primero califica este chat.'),
            'next_prompt': t(lang, 'Was this helpful?', 'Was dit nuttig?', 'Fue util esta conversacion?'),
            'quick_replies': [('yes', 'Yes'), ('no', 'No')],
            'done': False,
        }))

    if state.get('awaiting_post_save_choice'):
        if lower_text in {'continue_ai', 'continue', 'assistant', 'ai', 'continue with assistant', 'view quote', 'view'}:
            # Keep awaiting_post_save_choice TRUE so Revise/Done still work
            state['exact_quote_ready'] = True
            quote = calculate_exact_quote(state.get('collected', {}))
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 
                    f"Your quote: ${quote['total']} (base ${quote['base']}, add-ons ${quote['addon']}, timeline {quote['timeline_multiplier']}x).", 
                    f"Uw offerte: ${quote['total']} (basis ${quote['base']}, add-ons ${quote['addon']}, tijdlijn {quote['timeline_multiplier']}x).",
                    f"Tu cotizacion: ${quote['total']} (base ${quote['base']}, extras ${quote['addon']}, tiempo {quote['timeline_multiplier']}x)."
                ),
                'next_prompt': t(lang, 'What would you like to do next?', 'Wat wilt u nu doen?', 'Que te gustaria hacer ahora?'),
                'quick_replies': [('revise_quote', 'Revise Quote'), ('human', 'Talk to Human'), ('done', 'Done for Now')],
                'done': False,
            }))
        if lower_text in {'revise_quote', 'revise', 'change', 'edit'}:
            state['awaiting_post_save_choice'] = False
            state['awaiting_edit_choice'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'What would you like to change?', 'Wat wilt u wijzigen?', 'Que quieres cambiar?'),
                'next_prompt': t(lang, 'Pick a field to edit.', 'Kies een veld om te bewerken.', 'Elige un campo para editar.'),
                'quick_replies': edit_choice_quick_replies(),
                'done': False,
            }))
        if lower_text in {'done', 'done for now', 'finish', 'bye'}:
            state['awaiting_post_save_choice'] = False
            state['awaiting_csat'] = True
            state['csat_lead_id'] = state.get('completed_lead_id')
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Thanks for using Tasky. Quick question: was this helpful?', 'Bedankt voor het gebruik van Tasky. Snelle vraag: was dit nuttig?', 'Gracias por usar Tasky. Pregunta rapida: fue esto util?'),
                'next_prompt': '',
                'quick_replies': [('yes', 'Yes'), ('no', 'No')],
                'done': False,
            }))
        if lower_text in {'human', 'talk to human', 'team', 'agent'}:
            state['awaiting_post_save_choice'] = False
            state['collected']['contact_preference'] = 'human'
            lead = Lead.objects.filter(id=state.get('completed_lead_id')).first()
            if lead:
                lead.contact_preference = 'human'
                lead.needs_human = True
                lead.stage = 'human_handoff'
                lead.save(update_fields=['contact_preference', 'needs_human', 'stage'])
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Connecting you with a teammate.', 'U wordt verbonden met een teamlid.', 'Conectandote con un companero.'),
                'next_prompt': t(lang, 'A teammate will contact you shortly.', 'Een teamlid neemt snel contact op.', 'Un companero te contactara pronto.'),
                'quick_replies': [],
                'done': True,
                'redirect_url': '/human/',
            }))
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Choose an action below.', 'Kies een actie hieronder.', 'Elige una accion abajo.'),
            'next_prompt': '',
            'quick_replies': [('continue_ai', 'View Quote'), ('revise_quote', 'Revise'), ('human', 'Talk to Human')],
            'done': False,
        }))

    if state.get('awaiting_csat_comment'):
        lead = Lead.objects.filter(id=state.get('csat_lead_id')).first()
        if lead and lower_text not in {'skip', 'no', 'none'}:
            lead.csat_comment = text
            lead.save(update_fields=['csat_comment'])
        state['awaiting_csat_comment'] = False
        state['csat_lead_id'] = None
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Thank you. Your feedback is saved.', 'Dank u. Uw feedback is opgeslagen.', 'Gracias. Tu comentario fue guardado.'),
            'next_prompt': t(lang, 'You can continue here anytime.', 'U kunt hier altijd doorgaan.', 'Puedes continuar aqui cuando quieras.'),
            'quick_replies': [],
            'done': True,
            'redirect_url': '/human/' if state.get('collected', {}).get('contact_preference') == 'human' else '',
        }))

    if state.get('awaiting_confirmation'):
        if lower_text in {'confirm', 'confirm_save', 'yes'}:
            lead, qualification = finish_chat_lead(request, state)
            labels = build_process_labels(lead)
            analyzer = analyze_process_state(state.get('collected', {}))
            state['awaiting_confirmation'] = False
            state['awaiting_post_save_choice'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(
                    lang,
                    'Perfect. Your details are saved and your draft quote is ready.',
                    'Perfect. Uw gegevens zijn opgeslagen en uw conceptofferte is klaar.',
                    'Perfecto. Tus datos estan guardados y tu borrador de cotizacion esta listo.',
                ),
                'next_prompt': t(lang, 'Would you like to continue with me, or should I connect you with a human teammate?', 'Wilt u met mij doorgaan, of zal ik u verbinden met een collega?', 'Quieres continuar conmigo o prefieres que te conecte con un companero humano?'),
                'quick_replies': [('continue_ai', 'Continue with Assistant'), ('human', 'Talk to Human')],
                'done': False,
                'labels': labels,
                'analyzer': analyzer,
            }))
        if lower_text in {'edit', 'edit_details'}:
            state['awaiting_edit_choice'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Choose what you want to edit.', 'Kies wat u wilt aanpassen.', 'Elige que deseas editar.'),
                'next_prompt': t(lang, 'Tap one field below.', 'Tik hieronder een veld aan.', 'Toca un campo abajo.'),
                'quick_replies': edit_choice_quick_replies(),
                'done': False,
            }))
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Please confirm or edit before saving.', 'Bevestig of wijzig eerst voordat u opslaat.', 'Confirma o edita antes de guardar.'),
            'next_prompt': t(lang, 'Confirm details?', 'Details bevestigen?', 'Confirmar datos?'),
            'quick_replies': [('confirm', 'Confirm & Save'), ('edit', 'Edit Details'), ('start over', 'Start Over')],
            'done': False,
        }))

    if state.get('awaiting_edit_choice'):
        if lower_text.startswith('edit:'):
            field = lower_text.split(':', 1)[1]
            if field in MANDATORY_FIELDS:
                state.get('collected', {}).pop(field, None)
                if field in state.get('answered_fields', []):
                    state['answered_fields'] = [f for f in state['answered_fields'] if f != field]
                state['awaiting_edit_choice'] = False
                state['awaiting_confirmation'] = False
                sync_step_index(state)
                step = current_step(state) or CHAT_STEPS[0]
                request.session['assistant_state'] = state
                return JsonResponse(enrich_response(state, {
                    'message': t(lang, f'{field_label(field).title()} cleared.', f'{field_label(field).title()} gewist.', f'{field_label(field).title()} eliminado.'),
                    'next_prompt': prompt_for_step(step, lang, state),
                    'quick_replies': quick_replies_for_state(state),
                    'done': False,
                }))
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Please select one field from the list.', 'Kies een veld uit de lijst.', 'Selecciona un campo de la lista.'),
            'next_prompt': t(lang, 'Tap one field below.', 'Tik hieronder een veld aan.', 'Toca un campo abajo.'),
            'quick_replies': edit_choice_quick_replies(),
            'done': False,
        }))

    if requests_crm_or_erp(text):
        detected_budget = extract_budget_range(text)
        state['collected']['project_type'] = 'custom'
        mark_field_answered(state, 'project_type')
        if detected_budget:
            state['collected']['budget_range'] = detected_budget
            mark_field_answered(state, 'budget_range')
        sync_derived_fields(state)
        sync_step_index(state)

        budget_check = budget_validation_result(state.get('collected', {}))
        if not budget_check.get('ok'):
            state['awaiting_budget_resolution'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(
                    lang,
                    f"For CRM/ERP systems, typical pricing starts around ${budget_check['minimum']}. Your selected budget is below that.",
                    f"Voor CRM/ERP-systemen start de prijs meestal rond ${budget_check['minimum']}. Uw gekozen budget ligt daaronder.",
                    f"Para sistemas CRM/ERP, el precio suele empezar alrededor de ${budget_check['minimum']}. Tu presupuesto seleccionado esta por debajo.",
                ),
                'next_prompt': t(lang, 'Would you like a simpler solution, budget adjustment, or human support?', 'Wilt u een eenvoudiger oplossing, budgetaanpassing of menselijke ondersteuning?', 'Prefieres una solucion simple, ajustar presupuesto o soporte humano?'),
                'quick_replies': [
                    ('downgrade_service', 'Suggest Simpler Solution'),
                    ('adjust_budget', 'Adjust Budget'),
                    ('human', 'Talk to Human'),
                ],
                'done': False,
            }))

        if not detected_budget and not is_field_complete(state, 'budget_range'):
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(
                    lang,
                    'Got it. CRM/ERP is a serious build, so let us do a quick stage-fit check first.',
                    'Begrepen. CRM/ERP is een serieuze build, dus laten we eerst een snelle haalbaarheidscheck doen.',
                    'Entendido. CRM/ERP es una implementacion seria, asi que hagamos primero una comprobacion rapida.',
                ),
                'next_prompt': t(lang, 'Which budget range are you targeting for this?', 'Welk budgetbereik mikt u hiervoor?', 'Que rango de presupuesto manejas para esto?'),
                'quick_replies': FIELD_CONFIG['budget_range'].get('quick_replies', []),
                'done': False,
            }))

        next_step = current_step(state)
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(
                lang,
                'Great. Based on your input, CRM/ERP can be a viable direction.',
                'Prima. Op basis van uw input kan CRM/ERP een haalbare richting zijn.',
                'Perfecto. Segun tu informacion, CRM/ERP puede ser una direccion viable.',
            ),
            'next_prompt': prompt_for_step(next_step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if asks_services(text):
        step = current_step(state) or CHAT_STEPS[0]
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(
                lang,
                'Divi Hosting services: CMS, Ecommerce, AI, Flutter, Custom Development, Video, Graphic Design, Social Promotion, and Hosting.',
                'Divi Hosting diensten: CMS, Ecommerce, AI, Flutter, Custom Development, Video, Graphic Design, Social Promotion en Hosting.',
                'Servicios de Divi Hosting: CMS, Ecommerce, AI, Flutter, Desarrollo a Medida, Video, Diseno Grafico, Promocion Social y Hosting.',
            ),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if asks_pricing(text):
        step = current_step(state) or CHAT_STEPS[0]
        project_type = state.get('collected', {}).get('project_type', 'cms')
        rough = rough_range_for_divi_service(project_type)
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, f'Rough range: {rough}. Final quote after intake.', f'Ruwe prijs: {rough}. Definitieve offerte na intake.', f'Rango estimado: {rough}. La cotizacion final llega despues de la toma de requisitos.'),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if wants_human(text):
        state['collected']['contact_preference'] = 'human'
        lead, qualification = finish_chat_lead(request, state)
        request.session['assistant_state'] = state
        labels = build_process_labels(lead)
        analyzer = analyze_process_state(state.get('collected', {}))
        return JsonResponse(enrich_response(state, {
            'message': t(
                lang,
                'Done. A human teammate will contact you within 30 minutes during business hours.',
                'Klaar. Een collega neemt binnen 30 minuten contact op tijdens kantooruren.',
                'Listo. Un companero humano te contactara en 30 minutos durante horario laboral.',
            ),
            'next_prompt': t(
                lang,
                'A human teammate will continue this conversation from here.',
                'Een collega neemt dit gesprek vanaf hier over.',
                'Un companero humano continuara esta conversacion desde aqui.',
            ),
            'quick_replies': [],
            'done': True,
            'redirect_url': '/human/',
            'lead_id': lead.id,
            'labels': labels,
            'analyzer': analyzer,
        }))

    if is_greeting_text(text) and state.get('step_index', 0) == 0:
        seen_intro = state.get('seen_intro', False)
        state['seen_intro'] = True
        step = current_step(state) or CHAT_STEPS[0]
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': greeting_message(lang, seen_intro),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    uncertainty_markers = {
        "i don't know",
        "i dont know",
        "not sure",
        "i don't think",
        "i dont think",
        "idk",
        "maybe",
    }
    if text.lower().strip() in uncertainty_markers:
        step = current_step(state) or CHAT_STEPS[0]
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(
                lang,
                'No problem. Please choose the next required option below.',
                'Geen probleem. Kies hieronder de volgende verplichte optie.',
                'Sin problema. Elige abajo la siguiente opcion obligatoria.',
            ),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if likely_nonsense(text):
        step = current_step(state) or CHAT_STEPS[0]
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'I could not understand that yet. Use one option below and I will guide you.', 'Ik begreep dat nog niet. Kies hieronder een optie en ik begeleid u.', 'Aun no pude entenderlo. Usa una opcion de abajo y te guio.'),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    if is_smalltalk_or_offtopic(text):
        step = current_step(state) or CHAT_STEPS[0]
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Thanks. I will keep this simple and guide you.', 'Dank u. Ik houd het eenvoudig en begeleid u.', 'Gracias. Lo mantendre simple y te guiare.'),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    step = current_step(state)
    if not step:
        if state.get('completed_lead_id'):
            # Check if user wants human follow-up (handle typos)
            if lower_text in {'yes', 'yess', 'yea', 'yeah', 'y', 'human', 'talk to human', 'agent'}:
                state['collected']['contact_preference'] = 'human'
                lead = Lead.objects.filter(id=state.get('completed_lead_id')).first()
                if lead:
                    lead.contact_preference = 'human'
                    lead.needs_human = True
                    lead.stage = 'human_handoff'
                    lead.save(update_fields=['contact_preference', 'needs_human', 'stage'])
                request.session['assistant_state'] = state
                return JsonResponse(enrich_response(state, {
                    'message': t(lang, 'Connecting you with a teammate.', 'U wordt verbonden met een teamlid.', 'Conectandote con un companero.'),
                    'next_prompt': t(lang, 'A teammate will contact you shortly.', 'Een teamlid neemt snel contact op.', 'Un companero te contactara pronto.'),
                    'quick_replies': [],
                    'done': True,
                    'redirect_url': '/human/',
                }))
            if lower_text in {'no', 'nope', 'n', 'done', 'bye', 'finish'}:
                request.session['assistant_state'] = state
                return JsonResponse(enrich_response(state, {
                    'message': t(lang, 'Thanks for using Tasky. Your quote is saved.', 'Bedankt voor Tasky. Uw offerte is opgeslagen.', 'Gracias por usar Tasky. Tu cotizacion esta guardada.'),
                    'next_prompt': '',
                    'quick_replies': [],
                    'done': True,
                }))
            # Default prompt for saved lead
            state['awaiting_post_save_choice'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Your lead is already saved.', 'Uw lead is al opgeslagen.', 'Tu lead ya fue guardado.'),
                'next_prompt': t(lang, 'What would you like to do?', 'Wat wilt u doen?', 'Que te gustaria hacer?'),
                'quick_replies': [('continue_ai', 'View Quote'), ('revise_quote', 'Revise'), ('human', 'Talk to Human')],
                'done': False,
            }))

        _analyzer = analyze_process_state(state.get('collected', {}))
        _pending = pending_risk_check_field(state, _analyzer)
        if _pending:
            _risk_step = FIELD_CONFIG[_pending]
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang,
                    'Almost done. One quick check before we confirm your lead.',
                    'Bijna klaar. Nog een korte controle voor bevestiging.',
                    'Casi listo. Una comprobacion rapida antes de confirmar.',
                ),
                'next_prompt': _risk_step['prompt'].get(lang) or _risk_step['prompt']['en'],
                'quick_replies': _risk_step.get('quick_replies', []),
                'done': False,
            }))
        state['awaiting_confirmation'] = True
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'Please review your details before final save.', 'Controleer uw gegevens voor definitief opslaan.', 'Revisa tus datos antes del guardado final.'),
            'next_prompt': ' | '.join(intake_review_lines(state)),
            'quick_replies': [('confirm', 'Confirm & Save'), ('edit', 'Edit Details'), ('start over', 'Start Over')],
            'done': False,
        }))

    if step and step['field'] == 'name' and is_greeting_text(text):
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': greeting_message(lang),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    extracted = extract_fields_from_message(text, state)
    if extracted:
        saved_fields = save_extracted_fields(state, extracted)
        analyzer = analyze_process_state(state.get('collected', {}))
        budget_check = budget_validation_result(state.get('collected', {}))
        if not budget_check.get('ok'):
            state['awaiting_budget_resolution'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(
                    lang,
                    f"For this service, typical pricing starts around ${budget_check['minimum']}. Your selected budget is below that.",
                    f"Voor deze service start de prijs meestal rond ${budget_check['minimum']}. Uw gekozen budget ligt daaronder.",
                    f"Para este servicio, el precio suele empezar alrededor de ${budget_check['minimum']}. Tu presupuesto seleccionado esta por debajo.",
                ),
                'next_prompt': t(lang, 'Would you like a simpler solution, budget adjustment, or human support?', 'Wilt u een eenvoudiger oplossing, budgetaanpassing of menselijke ondersteuning?', 'Prefieres una solucion simple, ajustar presupuesto o soporte humano?'),
                'quick_replies': [
                    ('downgrade_service', 'Suggest Simpler Solution'),
                    ('adjust_budget', 'Adjust Budget'),
                    ('human', 'Talk to Human'),
                ],
                'done': False,
            }))
        if not current_step(state):
            _pending = pending_risk_check_field(state, analyzer)
            if _pending:
                _risk_step = FIELD_CONFIG[_pending]
                request.session['assistant_state'] = state
                return JsonResponse(enrich_response(state, {
                    'message': t(lang,
                        f"{summarize_saved_fields(saved_fields, lang)} Almost done — one quick check needed.",
                        f"{summarize_saved_fields(saved_fields, lang)} Bijna klaar — nog een korte controle.",
                        f"{summarize_saved_fields(saved_fields, lang)} Casi listo — una comprobacion rapida.",
                    ),
                    'next_prompt': _risk_step['prompt'].get(lang) or _risk_step['prompt']['en'],
                    'quick_replies': _risk_step.get('quick_replies', []),
                    'done': False,
                }))
            state['awaiting_confirmation'] = True
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang, 'Great. Your intake is complete. Please confirm before final save.', 'Top. Uw intake is compleet. Bevestig voor definitief opslaan.', 'Perfecto. Tu intake esta completo. Confirma antes de guardar.'),
                'next_prompt': ' | '.join(intake_review_lines(state)),
                'quick_replies': [('confirm', 'Confirm & Save'), ('edit', 'Edit Details'), ('start over', 'Start Over')],
                'done': False,
                'analyzer': analyzer,
            }))

        request.session['assistant_state'] = state
        next_step = current_step(state)
        response_message = summarize_saved_fields(saved_fields, lang)
        if next_step and next_step['field'] == 'selected_features':
            response_message = recommendation_message(state, lang)
        else:
            response_message = compose_guided_message(
                response_message,
                business_insight_for_next_step(state, next_step, lang),
            )
        return JsonResponse(enrich_response(state, {
            'message': response_message,
            'next_prompt': prompt_for_step(next_step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
            'analyzer': analyzer,
        }))

    text = normalize_choice_value(step, text)

    if not validate_step(step, text):
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': invalid_step_message(step, lang),
            'next_prompt': prompt_for_step(step, lang, state),
            'quick_replies': quick_replies_for_state(state),
            'done': False,
        }))

    state['collected'][step['field']] = parse_value(step['field'], text)
    sync_derived_fields(state)
    mark_field_answered(state, step['field'])
    sync_step_index(state)
    analyzer = analyze_process_state(state.get('collected', {}))
    budget_check = budget_validation_result(state.get('collected', {}))
    if not budget_check.get('ok'):
        state['awaiting_budget_resolution'] = True
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(
                lang,
                f"For this service, typical pricing starts around ${budget_check['minimum']}. Your selected budget is below that.",
                f"Voor deze service start de prijs meestal rond ${budget_check['minimum']}. Uw gekozen budget ligt daaronder.",
                f"Para este servicio, el precio suele empezar alrededor de ${budget_check['minimum']}. Tu presupuesto seleccionado esta por debajo.",
            ),
            'next_prompt': t(lang, 'Would you like a simpler solution, budget adjustment, or human support?', 'Wilt u een eenvoudiger oplossing, budgetaanpassing of menselijke ondersteuning?', 'Prefieres una solucion simple, ajustar presupuesto o soporte humano?'),
            'quick_replies': [
                ('downgrade_service', 'Suggest Simpler Solution'),
                ('adjust_budget', 'Adjust Budget'),
                ('human', 'Talk to Human'),
            ],
            'done': False,
        }))

    if not current_step(state):
        _pending = pending_risk_check_field(state, analyzer)
        if _pending:
            _risk_step = FIELD_CONFIG[_pending]
            request.session['assistant_state'] = state
            return JsonResponse(enrich_response(state, {
                'message': t(lang,
                    'Almost done. One quick check before we confirm your lead.',
                    'Bijna klaar. Nog een korte controle voor bevestiging.',
                    'Casi listo. Una comprobacion rapida antes de confirmar.',
                ),
                'next_prompt': _risk_step['prompt'].get(lang) or _risk_step['prompt']['en'],
                'quick_replies': _risk_step.get('quick_replies', []),
                'done': False,
            }))
        state['awaiting_confirmation'] = True
        request.session['assistant_state'] = state
        return JsonResponse(enrich_response(state, {
            'message': t(lang, 'All required details captured. Please confirm before final save.', 'Alle verplichte gegevens zijn vastgelegd. Bevestig voor definitief opslaan.', 'Todos los datos obligatorios estan listos. Confirma antes de guardar.'),
            'next_prompt': ' | '.join(intake_review_lines(state)),
            'quick_replies': [('confirm', 'Confirm & Save'), ('edit', 'Edit Details'), ('start over', 'Start Over')],
            'done': False,
            'analyzer': analyzer,
        }))

    next_step = current_step(state)
    response_message = ai_micro_response(step, lang, state, text)
    if next_step and next_step['field'] == 'selected_features':
        response_message = recommendation_message(state, lang)
    else:
        response_message = compose_guided_message(
            response_message,
            business_insight_for_next_step(state, next_step, lang),
        )
    request.session['assistant_state'] = state
    return JsonResponse(enrich_response(state, {
        'message': response_message,
        'next_prompt': prompt_for_step(next_step, lang, state),
        'quick_replies': quick_replies_for_state(state),
        'done': False,
        'analyzer': analyzer,
    }))


# 1️⃣ SALES
def sales_view(request):
    form = SalesForm()
    qualification_feedback = None

    if request.method == "POST":
        # If a low-score lead was already saved, allow manual override to continue intake.
        if request.POST.get('force_intake') == '1':
            existing_lead_id = request.session.get('lead_id')
            if existing_lead_id:
                return redirect('intake')

        form = SalesForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            detected_source, campaign, detected_by = detect_source(request)
            source_override = data.get('source_override') or 'auto'
            source = detected_source if source_override == 'auto' else source_override
            source_detected_by = detected_by if source_override == 'auto' else 'manual_override'
            assets_ready = data['logo_ready'] and data['content_ready'] and data['images_ready']

            qualification = evaluate_lead(
                phone=data['phone'],
                project_type=data['project_type'],
                timeline=data['timeline'],
                budget_range=data['budget_range'],
                is_decision_maker=data['is_decision_maker'],
                business_ready=data['business_ready'],
                willing_to_call=data['willing_to_call'],
                can_pay_deposit=data['can_pay_deposit'],
                assets_ready=assets_ready,
                current_presence_link=data['current_presence_link'],
            )

            recommended, reason = recommend_service(
                data['project_type'],
                data['primary_goal'],
                data['business_ready']
            )

            stage = 'qualified' if qualification['is_serious'] else 'unqualified'
            rough_price = rough_range_for_project(recommended) if qualification['is_serious'] else ''
            needs_human = data['contact_preference'] == 'human'

            if needs_human:
                stage = 'human_handoff'

            disqualification_reason = reason
            if not qualification['is_serious']:
                disqualification_reason = qualification['reason'] or disqualification_reason

            lead = Lead.objects.create(
                name=data['name'],
                email=data['email'],
                phone=data['phone'],
                first_message=data['first_message'],
                first_message_summary=summarize_first_message(data['first_message']),
                business_name=data['business_name'],
                current_presence_link=data['current_presence_link'],
                client_need=data['client_need'],
                client_need_details=data['client_need_details'],
                expected_benefit=data['expected_benefit'],
                expected_benefit_details=data['expected_benefit_details'],
                willing_to_call=data['willing_to_call'],
                can_pay_deposit=data['can_pay_deposit'],
                assets_ready=assets_ready,
                logo_ready=data['logo_ready'],
                content_ready=data['content_ready'],
                images_ready=data['images_ready'],
                source=source,
                source_campaign=campaign,
                source_detected_by=source_detected_by,
                project_type=data['project_type'],
                primary_goal=data['primary_goal'],
                budget_range=data['budget_range'],
                is_decision_maker=data['is_decision_maker'],
                business_ready=data['business_ready'],
                timeline=data['timeline'],
                contact_preference=data['contact_preference'],
                stage=stage,
                lead_score=qualification['score'],
                seriousness_level=qualification['seriousness_level'],
                next_action=qualification['next_action'],
                is_serious=qualification['is_serious'],
                needs_human=needs_human,
                recommended_service=recommended,
                disqualification_reason=disqualification_reason,
                rough_price=rough_price
            )

            schedule_default_followups(lead)
            if data['first_message']:
                log_communication(
                    lead=lead,
                    channel='whatsapp',
                    direction='inbound',
                    message_type='lead_message',
                    content=data['first_message'],
                )

            request.session['lead_id'] = lead.id
            request.session['rough_price'] = rough_price

            # RULE: Human selected -> stop AI flow and route to handoff page.
            if needs_human:
                return redirect('human_page')

            # RULE: only qualified leads (score >= 5) move to intake.
            if not qualification['can_move_to_intake']:
                qualification_feedback = {
                    'score': qualification['score'],
                    'level': qualification['seriousness_level'],
                    'next_action': qualification['next_action'],
                    'can_override': True,
                }
                return render(request, 'sales.html', {
                    'form': form,
                    'qualification_feedback': qualification_feedback,
                })

            return redirect('intake')

    return render(request, 'sales.html', {
        'form': form,
        'qualification_feedback': qualification_feedback,
    })


# 2️⃣ INTAKE
def intake_view(request):
    lead_id = request.session.get('lead_id')
    if not lead_id:
        return redirect('sales')

    lead = Lead.objects.get(id=lead_id)
    form = IntakeForm(project_type=lead.project_type)

    if request.method == "POST":
        form = IntakeForm(request.POST, project_type=lead.project_type)

        if form.is_valid():
            addons = form.cleaned_data['addons']
            is_complete = bool(
                form.cleaned_data.get('content')
                and form.cleaned_data.get('branding_ready')
            )

            intake = Intake.objects.create(
                lead=lead,
                pages=form.cleaned_data['pages'] or 1,
                addons=",".join(addons),
                content=form.cleaned_data['content'],
                branding_ready=form.cleaned_data['branding_ready'],
                integrations=form.cleaned_data['integrations'],
                ecommerce_platform=form.cleaned_data.get('ecommerce_platform', ''),
                ai_package=form.cleaned_data.get('ai_package', ''),
                custom_package=form.cleaned_data.get('custom_package', ''),
                timeline_confirm=form.cleaned_data['timeline_confirm'],
                is_complete=is_complete,
            )

            request.session['intake_id'] = intake.id

            return redirect('quote')

    return render(request, 'intake.html', {'form': form, 'lead': lead})


# 3️⃣ PRICING (MAIN LOGIC)
def quote_view(request):
    intake_id = request.session.get('intake_id')
    if not intake_id:
        return redirect('intake')

    intake = Intake.objects.get(id=intake_id)

    lead = intake.lead
    quote_service = lead.recommended_service if lead.recommended_service in ('cms', 'ecommerce', 'ai', 'custom', 'social_promotion') else lead.project_type
    quote_data = calculate_quote(quote_service, intake, lead.timeline)
    total = quote_data['total']
    monthly_cost = quote_data['monthly_cost']
    breakdown = quote_data['breakdown']
    notes = quote_data['notes']

    if quote_service != lead.project_type:
        notes.append(f"Requested service: {lead.project_type}. Recommended path: {quote_service}.")

    quote = Quote.objects.create(
        intake=intake,
        total_price=total,
        monthly_cost=monthly_cost if monthly_cost else None,
        breakdown="\n".join(breakdown),
        notes="\n".join(notes),
        status='sent',
    )

    invoice = create_invoice_from_quote(lead=lead, quote=quote)
    log_communication(
        lead=lead,
        invoice=invoice,
        channel='email',
        direction='outbound',
        message_type='quote_sent',
        content=f'Quote #{quote.id} and invoice {invoice.invoice_number} sent to client.',
    )

    lead.stage = 'proposal_sent'
    lead.save(update_fields=['stage'])

    return render(request, 'quote.html', {
        'total': total,
        'monthly_cost': monthly_cost,
        'breakdown': breakdown,
        'notes': notes,
        'rough_price': lead.rough_price
    })


# SUCCESS PAGE
def success_view(request):
    return render(request, 'success.html')


# HUMAN PAGE
def human_page(request):
    return render(request, 'human.html')


@require_POST
def mark_invoice_paid(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    invoice.status = 'paid'
    invoice.outstanding_balance = 0
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=['status', 'outstanding_balance', 'paid_at'])

    project = activate_project_after_payment(invoice)
    lead = invoice.lead
    lead.stage = 'won'
    lead.save(update_fields=['stage'])

    log_communication(
        lead=lead,
        invoice=invoice,
        project=project,
        channel='email',
        direction='outbound',
        message_type='payment_confirmed',
        content=f'Payment received for {invoice.invoice_number}. Project activated.',
    )

    return JsonResponse({
        'ok': True,
        'invoice_id': invoice.id,
        'project_id': project.id if project else None,
        'lead_stage': lead.stage,
    })


@require_POST
def send_weekly_update(request, project_id):
    project = get_object_or_404(ProjectExecution, id=project_id)
    log = weekly_progress_update(project)
    return JsonResponse({
        'ok': True,
        'project_id': project.id,
        'log_id': log.id,
    })