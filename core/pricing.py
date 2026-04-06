"""
Divi Hosting Pricing Rules & Configuration
Complete pricing catalog based on Maheshika's price list with 50% discount applied
"""

PRICING_CONFIG = {
    'cms_websites': {
        'wordpress_1page': {
            'name': '1-Page Website (WordPress)',
            'base_price': 149,
            'includes': ['Divi Theme', 'SEO basics', 'WhatsApp', 'Analytics', 'Security basics'],
            'timeline_days': 5,
        },
        'wordpress_5page': {
            'name': '5-Page Website (WordPress)',
            'base_price': 299,
            'includes': ['Divi Theme', 'SEO basics', 'WhatsApp', 'Analytics', 'Security basics'],
            'timeline_days': 10,
        },
        'wix_1page': {
            'name': '1-Page Website (Wix)',
            'base_price': 199,
            'includes': ['Wix builder', 'SSL', 'Mobile responsive'],
            'timeline_days': 5,
            'client_pays_monthly': 'Wix hosting ~$10-25/month',
        },
        'wix_5page': {
            'name': '5-Page Website (Wix)',
            'base_price': 349,
            'includes': ['Wix builder', 'SSL', 'Mobile responsive'],
            'timeline_days': 10,
            'client_pays_monthly': 'Wix hosting ~$10-25/month',
        },
        'squarespace_1page': {
            'name': '1-Page Website (Squarespace)',
            'base_price': 199,
            'includes': ['Template design', 'SSL', 'Mobile responsive'],
            'timeline_days': 5,
            'client_pays_monthly': 'Squarespace hosting ~$16-30/month',
        },
        'squarespace_5page': {
            'name': '5-Page Website (Squarespace)',
            'base_price': 349,
            'includes': ['Template design', 'SSL', 'Mobile responsive'],
            'timeline_days': 10,
            'client_pays_monthly': 'Squarespace hosting ~$16-30/month',
        },
        'webflow_1page': {
            'name': '1-Page Website (Webflow)',
            'base_price': 249,
            'includes': ['Webflow builder', 'Design flexibility', 'Animations'],
            'timeline_days': 7,
            'client_pays_monthly': 'Webflow hosting ~$18-35/month',
        },
        'webflow_5page': {
            'name': '5-Page Website (Webflow)',
            'base_price': 399,
            'includes': ['Webflow builder', 'Design flexibility', 'Animations'],
            'timeline_days': 15,
            'client_pays_monthly': 'Webflow hosting ~$18-35/month',
        },
    },
    'cms_addons': {
        'seo_pro': {'name': 'SEO Pro Package', 'price': 150, 'recurring': 59, 'recurring_period': 'yearly'},
        'speed_optimization': {'name': 'Speed Optimization', 'price': 150, 'recurring': 59, 'recurring_period': 'yearly'},
        'multilingual_5page': {'name': 'Multilingual (5 pages)', 'price': 100, 'recurring': 0},
        'booking_system': {'name': 'Booking System', 'price': 100, 'recurring': 79, 'recurring_period': 'yearly'},
        'security': {'name': 'Security Setup', 'price': 100, 'recurring': 199, 'recurring_period': 'yearly', 'recurring_optional': True},
        'backup_setup': {'name': 'Backup Setup', 'price': 60, 'recurring': 0},
        'mailchimp_setup': {'name': 'Mailchimp Setup', 'price': 75, 'recurring': 0, 'range': (50, 100)},
        'live_chat': {'name': 'Live Chat', 'price': 30, 'recurring': 0},
    },
    'cms_content_management_monthly': {
        'basic': {'hours': 6, 'price': 50},
        'standard': {'hours': 15, 'price': 100},
        'advanced': {'hours': 25, 'price': 150},
    },
    'ecommerce': {
        'woocommerce_basic': {
            'name': 'WooCommerce Basic Store',
            'base_price': 450,
            'includes': ['up to 10 pages', '50 products', 'cart', 'checkout', 'payments', 'PDF invoices', 'email templates', 'SEO basics'],
            'timeline_days': 12,
        },
        'magento_basic': {
            'name': 'Magento 2 Basic',
            'base_price': 900,
            'includes': ['Luma theme', '50 products', 'basic shipping/tax rules', 'PDF invoices', 'SEO basics'],
            'timeline_days': 15,
        },
    },
    'ecommerce_addons': {
        'woocommerce': {
            'payment_integration': {'name': 'Payment Integration', 'price': 75, 'recurring': 0},
            'subscriptions': {'name': 'Subscriptions', 'price': 100, 'recurring': 199, 'recurring_period': 'yearly'},
            'bookings': {'name': 'Bookings', 'price': 100, 'recurring': 249, 'recurring_period': 'yearly'},
            'multi_vendor': {'name': 'Multi-vendor', 'price': 150, 'recurring': 149, 'recurring_period': 'yearly'},
            'advanced_shipping': {'name': 'Advanced Shipping', 'price': 75, 'recurring': 99, 'recurring_period': 'yearly'},
        },
        'magento': {
            'one_step_checkout': {'name': 'One Step Checkout', 'price': 150, 'recurring': 300, 'recurring_period': 'yearly'},
            'seo_toolkit': {'name': 'SEO Toolkit', 'price': 150, 'recurring': 300, 'recurring_period': 'yearly'},
            'layered_navigation': {'name': 'Layered Navigation', 'price': 100, 'recurring': 0},
            'promotions_engine': {'name': 'Promotions Engine', 'price': 150, 'recurring': 0},
            'elasticsearch': {'name': 'ElasticSearch', 'price': 125, 'recurring': 0},
        },
    },
    'ecommerce_product_mgmt_monthly': {
        'basic': {'products': 50, 'price': 50},
        'standard': {'products': 150, 'price': 100},
        'advanced': {'products': 300, 'price': 150},
    },
    'ecommerce_content_mgmt_monthly': {
        'basic': {'hours': 6, 'price': 50},
        'standard': {'hours': 15, 'price': 100},
        'advanced': {'hours': 25, 'price': 150},
    },
    'ai_services': {
        'ai_chat_assistant': {
            'name': 'AI Chat Assistant',
            'setup': 125,
            'monthly': 100,
            'terms': ['Security deposit required', 'Usage limits apply', 'Changes: $30/hour (no discount)'],
        },
        'ai_booking_assistant': {
            'name': 'AI Booking Assistant',
            'setup': 200,
            'monthly': 120,
            'terms': ['Security deposit required', 'Usage limits apply', 'Changes: $30/hour (no discount)'],
        },
        'ai_business_assistant': {
            'name': 'AI Business Assistant',
            'setup': 250,
            'monthly': 150,
            'terms': ['Security deposit required', 'Usage limits apply', 'Changes: $30/hour (no discount)'],
        },
    },
    'flutter_apps': {
        'corporate_app': {
            'name': 'Corporate App (Android & iOS)',
            'base_price': 400,
            'includes': ['Android app', 'iOS app', 'API integration', 'Deployment'],
            'timeline_days': 20,
        },
        'booking_app': {
            'name': 'Booking App (Android & iOS)',
            'base_price': 600,
            'includes': ['Android app', 'iOS app', 'Booking system', 'Payments', 'Deployment'],
            'timeline_days': 25,
        },
    },
    'custom_development': {
        'hourly_rate': 15,
        'examples': {
            'crm': {'name': 'CRM System', 'estimate': 750, 'hours': 50},
            'erp': {'name': 'ERP System', 'estimate': 2000, 'hours': 133},
        },
    },
    'video_editing': {
        '30sec': {'name': 'Video Editing (30 sec)', 'price': 75},
        'extra_15sec': {'name': 'Extra 15 seconds', 'price': 20},
        'animation': {'name': 'Animation Video', 'price': 150},
    },
    'graphic_design': {
        'ai_logo': {'name': 'AI Logo Design', 'price': 30},
        'basic_logo': {'name': 'Basic Logo Design', 'price': 60},
        'custom_logo': {'name': 'Custom Logo Design', 'price': 125},
    },
    'social_promotion': {
        'campaign_setup': {'name': 'Campaign Setup', 'price': 75},
        'basic_monthly': {'name': 'Basic Monthly', 'price': 40},
        'standard_monthly': {'name': 'Standard Monthly', 'price': 75},
        'advanced_monthly': {'name': 'Advanced Monthly', 'price': 125},
    },
    'hosting': {
        'shared_basic': {'name': 'Shared Hosting Basic', 'price': 5, 'period': 'monthly', 'features': ['Unlimited domains', 'Unlimited storage', 'SSL', 'Email', 'Backups']},
        'shared_ecommerce': {'name': 'Shared Hosting E-commerce', 'price': 7.50, 'period': 'monthly', 'features': ['E-commerce optimized', 'SSL', 'Better performance', 'Increased DB', 'Backups']},
        'shared_plus': {'name': 'Shared Hosting Plus', 'price': 12.50, 'period': 'monthly', 'features': ['Premium support', 'Staging', 'Advanced caching', 'DDoS protection']},
        'vps': {'name': 'VPS', 'price': 30, 'period': 'monthly', 'features': ['2GB RAM', '40GB SSD', '2TB bandwidth', 'Root access', 'Managed support']},
        'vps_plus': {'name': 'VPS Plus', 'price': 45, 'period': 'monthly', 'features': ['4GB RAM', '80GB SSD', '4TB bandwidth', 'Root access', 'Priority support']},
        'dedicated_basic': {'name': 'Dedicated Basic', 'price': 75, 'period': 'monthly', 'features': ['Intel Xeon', '16GB RAM', '500GB SSD', 'Unlimited bandwidth', 'RAID', 'DDoS']},
        'dedicated_plus': {'name': 'Dedicated Plus', 'price': 110, 'period': 'monthly', 'features': ['Intel Xeon E5', '32GB RAM', '1TB SSD', 'Unlimited bandwidth', '24/7 managed', 'Advanced DDoS']},
        'dedicated_pro': {'name': 'Dedicated Pro', 'price': 175, 'period': 'monthly', 'features': ['Premium CPU (E5-2680)', '64GB RAM', '2TB NVMe SSD', 'Unlimited bandwidth', '24/7 management', 'Multi-IP']},
        'dedicated_advance': {'name': 'Dedicated Advance', 'price': 250, 'period': 'monthly', 'features': ['Top-tier CPU', '128GB RAM', '4TB NVMe SSD RAID-10', 'Unlimited bandwidth', 'Full management', 'HA setup']},
    },
    'hosting_addons': {
        'offserver_backup': {'name': 'Off-server Backup', 'price': 5, 'period': 'monthly'},
        'security': {'name': 'Security Add-on', 'price': 5, 'period': 'monthly'},
        'performance': {'name': 'Performance Add-on', 'price': 10, 'period': 'monthly'},
    },
    'support': {
        'onsite_hourly': {'name': 'On-site Support', 'price': 30, 'period': 'hourly', 'no_discount': True},
        'dev_changes_hourly': {'name': 'Development/Changes', 'price': 15, 'period': 'hourly'},
        'ai_changes_hourly': {'name': 'AI Model Changes', 'price': 30, 'period': 'hourly', 'no_discount': True},
    },
}

# Priority surcharges
PRIORITY_RULES = {
    'normal': {'multiplier': 1.0, 'label': 'Normal (7-10 days)'},
    'fast': {'multiplier': 1.2, 'label': 'Fast (3-5 days) - +20%'},
    'urgent': {'multiplier': 1.5, 'label': 'Urgent (1-2 days) - +50%'},
}

# Timeline-based pricing adjustments
TIMELINE_SURCHARGE = {
    'economy': {'days': 14, 'surcharge': 0},
    'standard': {'days': 7, 'surcharge': 0.1},
    'express': {'days': 3, 'surcharge': 0.25},
    'urgent': {'days': 1, 'surcharge': 0.5},
}


def calculate_project_price(base_price, priority='normal', addons=None):
    """
    Calculate total project price with priority surcharges and add-ons
    """
    if addons is None:
        addons = []
    
    # Apply priority multiplier
    multiplier = PRIORITY_RULES.get(priority, {}).get('multiplier', 1.0)
    total = base_price * multiplier
    
    # Add add-on prices
    for addon in addons:
        if isinstance(addon, dict):
            total += addon.get('price', 0)
    
    return round(total, 2)


def get_rough_price_estimate(project_type, service_type):
    """
    Provide rough pricing for early-stage leads (before full intake)
    """
    estimates = {
        'wordpress': {'1page': '$149', '5page': '$299'},
        'woocommerce': '$450 - $600 (with add-ons)',
        'magento': '$900 - $1200 (with add-ons)',
        'flutter': {'corporate': '$400', 'booking': '$600'},
        'custom': '$15/hour (typically $750-2000 for projects)',
        'ai': {'chat': '$125 setup + $100/month', 'booking': '$200 setup + $120/month'},
    }
    return estimates.get(service_type, 'Contact us for estimate')
