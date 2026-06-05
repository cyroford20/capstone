from django.core.management.base import BaseCommand
from api.models import Threshold

class Command(BaseCommand):
    help = 'Populate default sensor thresholds'

    def handle(self, *args, **options):
        defaults = [
            {'parameter': 'temperature', 'min_value': 20, 'max_value': 35, 'unit': '°C'},
            {'parameter': 'ph', 'min_value': 3.0, 'max_value': 8.0, 'unit': ''},
            {'parameter': 'turbidity', 'min_value': 25, 'max_value': 50, 'unit': 'NTU'},
            {'parameter': 'tds', 'min_value': 100, 'max_value': 160, 'unit': 'ppm'},
        ]

        for threshold_data in defaults:
            threshold, created = Threshold.objects.update_or_create(
                parameter=threshold_data['parameter'],
                defaults={
                    'min_value': threshold_data['min_value'],
                    'max_value': threshold_data['max_value'],
                    'unit': threshold_data['unit']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created threshold for {threshold.parameter}: {threshold.min_value}-{threshold.max_value} {threshold.unit}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✅ Updated threshold for {threshold.parameter}: {threshold.min_value}-{threshold.max_value} {threshold.unit}'))