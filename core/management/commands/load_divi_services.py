from django.core.management.base import BaseCommand
from core.models import ServiceCategory, ServicePackage, ServiceAddOn
from core.divi_services import DIVI_SERVICES


class Command(BaseCommand):
    help = 'Load Divi Hosting services, packages, and add-ons into database'

    def handle(self, *args, **options):
        self.stdout.write('Loading Divi Hosting services...')

        for category_slug, category_data in DIVI_SERVICES.items():
            # Create or get category
            category, created = ServiceCategory.objects.update_or_create(
                slug=category_slug,
                defaults={
                    'name': category_data['name'],
                    'description': category_data['description'],
                    'icon': category_data['icon'],
                    'order': list(DIVI_SERVICES.keys()).index(category_slug) + 1,
                }
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status} category: {category.name}')

            # Create packages
            for pkg_slug, pkg_data in category_data.get('packages', {}).items():
                package, created = ServicePackage.objects.update_or_create(
                    category=category,
                    name=pkg_data['name'],
                    defaults={
                        'description': pkg_data.get('name', ''),
                        'base_price': pkg_data['base_price'],
                        'platform': pkg_data.get('platform', ''),
                        'features': '\n'.join(pkg_data.get('features', [])),
                        'timeline_days': pkg_data.get('timeline_days', 5),
                    }
                )
                status = 'Created' if created else 'Updated'
                self.stdout.write(f'    {status} package: {package.name} (${package.base_price})')

            # Create add-ons
            for addon_slug, addon_data in category_data.get('addons', {}).items():
                addon, created = ServiceAddOn.objects.update_or_create(
                    category=category,
                    name=addon_data['name'],
                    defaults={
                        'description': addon_data.get('description', ''),
                        'price': addon_data['price'],
                        'price_unit': addon_data.get('unit', 'one-time'),
                    }
                )
                status = 'Created' if created else 'Updated'
                self.stdout.write(f'    {status} add-on: {addon.name} (${addon.price}/{addon.price_unit})')

        self.stdout.write(self.style.SUCCESS('✓ Successfully loaded all Divi Hosting services'))
        self.stdout.write(f'Total categories: {ServiceCategory.objects.count()}')
        self.stdout.write(f'Total packages: {ServicePackage.objects.count()}')
        self.stdout.write(f'Total add-ons: {ServiceAddOn.objects.count()}')
