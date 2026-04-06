"""Central rule definitions for qualification, recommendation, and pricing."""

ROUGH_PRICE_RANGES = {
    'cms': '$149 - $599',
    'ecommerce': '$450 - $900',
    'ai': '$125 setup + monthly plans',
    'custom': '$150 - $2000+',
    'social_promotion': '$40 - $125',
}

QUALIFICATION_WEIGHTS = {
    'is_decision_maker': 2,
    'can_pay_deposit': 2,
    'timeline_urgent': 2,
    'timeline_normal': 1,
    'budget_fit': 2,
    'willing_to_call': 1,
    'business_ready': 1,
    'assets_ready': 1,
}

SERVICE_MINIMUM = {
    'cms': 149,
    'ecommerce': 450,
    'ai': 125,
    'custom': 750,
    'flutter': 400,
    'video': 75,
    'design': 30,
    'social': 75,
    'hosting': 5,
    'social_promotion': 40,
}

BUDGET_CAP = {
    'very_low': 150,    # Under $150
    'low': 300,         # $150-300
    'mid': 1000,        # $300-1000
    'high': 3000,       # $1000-3000
    'premium': 10000,   # Above $3000
    'undecided': 500,   # Assume mid-range potential
}

ADDON_PRICES = {
    'seo': 150,
    'booking': 100,
    'security': 100,
}

ADDON_NOTES = {
    'seo': 'SEO Pro includes optional license (~$59/year).',
    'booking': 'Booking add-on may require license (~$79/year).',
    'security': 'Security includes optional advanced package (~$199/year).',
}

TIMELINE_SURCHARGE = {
    'normal': 0,
    'fast': 40,
    'urgent': 80,
}

AI_SETUP_PRICING = {
    'chat': 125,
    'booking': 200,
    'business': 250,
}

AI_MONTHLY_PRICING = {
    'chat': 100,
    'booking': 120,
    'business': 150,
}

CUSTOM_PRICING = {
    'hourly': 150,
    'crm': 750,
    'erp': 2000,
}


def rough_range_for_project(project_type):
    return ROUGH_PRICE_RANGES.get(project_type, 'Available after intake')


def is_budget_fit(project_type, budget_range):
    minimum = SERVICE_MINIMUM.get(project_type, 150)
    cap = BUDGET_CAP.get(budget_range, 0)
    return cap >= minimum and cap > 0


def evaluate_lead(
    phone,
    project_type,
    timeline,
    budget_range,
    is_decision_maker,
    business_ready,
    willing_to_call,
    can_pay_deposit,
    assets_ready,
    current_presence_link,
):
    score = 0
    reasons = []

    if not phone:
        reasons.append('Missing phone number')

    if is_budget_fit(project_type, budget_range):
        score += QUALIFICATION_WEIGHTS['budget_fit']
    else:
        reasons.append('Budget does not fit requested service')

    if is_decision_maker:
        score += QUALIFICATION_WEIGHTS['is_decision_maker']
    else:
        reasons.append('Contact is not decision maker')

    if timeline == 'urgent' or timeline == 'fast':
        score += QUALIFICATION_WEIGHTS['timeline_urgent']
    elif timeline == 'normal':
        score += QUALIFICATION_WEIGHTS['timeline_normal']

    if willing_to_call:
        score += QUALIFICATION_WEIGHTS['willing_to_call']
    else:
        reasons.append('Not willing to take a sales call yet')

    if can_pay_deposit:
        score += QUALIFICATION_WEIGHTS['can_pay_deposit']
    else:
        reasons.append('Deposit readiness not confirmed')

    if assets_ready:
        score += QUALIFICATION_WEIGHTS['assets_ready']
    else:
        reasons.append('Assets/content not ready')

    if current_presence_link:
        score += 0

    if business_ready:
        score += QUALIFICATION_WEIGHTS['business_ready']
    else:
        reasons.append('Business readiness is low')

    if assets_ready:
        score += QUALIFICATION_WEIGHTS['assets_ready']

    # Adjusted thresholds for chatbot leads (less friction than forms)
    if score >= 6:
        seriousness_level = 'hot'
        next_action = 'Call within 10 minutes and push to quotation.'
    elif score >= 4:
        seriousness_level = 'warm'
        next_action = 'Send quote and schedule call in 24 hours.'
    elif score >= 2:
        seriousness_level = 'interested'
        next_action = 'Send quote with nurture steps; follow up in 2 days.'
    else:
        seriousness_level = 'cold'
        next_action = 'Send info pack and follow up in 5 days.'

    can_move_to_intake = score >= 2 and bool(phone)
    is_serious = seriousness_level in ('hot', 'warm', 'interested') and can_move_to_intake
    return {
        'score': score,
        'seriousness_level': seriousness_level,
        'next_action': next_action,
        'can_move_to_intake': can_move_to_intake,
        'is_serious': is_serious,
        'reason': '; '.join(reasons),
    }


def recommend_service(project_type, primary_goal, business_ready):
    if primary_goal == 'social_only':
        return 'social_promotion', 'Client goal is social presence only; recommend social promotion first.'

    if project_type == 'ecommerce' and not business_ready:
        return 'cms', 'Client is not ecommerce-ready (delivery/ops missing); recommend CMS first.'

    return project_type, ''


def calculate_quote(service_type, intake, lead_timeline):
    total = 0.0
    monthly_cost = 0.0
    breakdown = []
    notes = []

    if service_type == 'cms':
        if intake.pages == 1:
            total += 149
            breakdown.append('1-page website: $149')
        else:
            total += 299
            breakdown.append('5-page website: $299')

    elif service_type == 'ecommerce':
        if intake.ecommerce_platform == 'magento':
            total += 900
            breakdown.append('Magento basic package: $900')
        else:
            total += 450
            breakdown.append('WooCommerce basic package: $450')

    elif service_type == 'ai':
        selected_ai = intake.ai_package or 'chat'
        setup_price = AI_SETUP_PRICING[selected_ai]
        monthly_cost = AI_MONTHLY_PRICING[selected_ai]
        total += setup_price
        breakdown.append(f'AI setup ({selected_ai}): ${setup_price}')
        notes.append(f'Monthly AI service: ${monthly_cost}')
        notes.append('Security deposit required; usage limits apply; changes billed at $30/hour.')

    elif service_type == 'custom':
        selected_custom = intake.custom_package or 'hourly'
        custom_total = CUSTOM_PRICING[selected_custom]
        total += custom_total
        if selected_custom == 'erp':
            breakdown.append('ERP project: $2000')
        elif selected_custom == 'crm':
            breakdown.append('CRM project: $750')
        else:
            breakdown.append('Hourly custom block (10h): $150')

    elif service_type == 'social_promotion':
        total += 75
        breakdown.append('Social campaign setup: $75')
        notes.append('Recommended path based on client goals.')

    addons = [item for item in intake.addons.split(',') if item]
    for addon in addons:
        if addon in ADDON_PRICES:
            price = ADDON_PRICES[addon]
            total += price
            breakdown.append(f'{addon.title()}: ${price}')
            if addon in ADDON_NOTES:
                notes.append(ADDON_NOTES[addon])

    chosen_timeline = intake.timeline_confirm or lead_timeline
    surcharge = TIMELINE_SURCHARGE.get(chosen_timeline, 0)
    if surcharge:
        total += surcharge
        label = 'Fast' if chosen_timeline == 'fast' else 'Urgent'
        breakdown.append(f'{label} delivery surcharge: ${surcharge}')

    return {
        'total': total,
        'monthly_cost': monthly_cost,
        'breakdown': breakdown,
        'notes': notes,
    }
