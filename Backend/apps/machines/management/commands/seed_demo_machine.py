"""
Seed a demo machine record for a given user.

Prefer loading the full fleet dataset instead:
  ..\\.venv\\Scripts\\python.exe initiliaze_database.py

Usage:
  python manage.py seed_demo_machine
  python manage.py seed_demo_machine --username USR-001
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Company
from apps.machines.models import Machine, MachineModel, MachineUnit

A3279_UNITS = [
    {'code': 'A', 'name': 'Caps sorter', 'note': 'Centrifugal sorter feeding oriented caps into the chute.', 'sort_order': 1},
    {'code': 'B', 'name': 'Caps chute', 'note': 'Drives caps from the sorter to the distribution head.', 'sort_order': 2},
    {'code': 'C', 'name': 'Distribution head', 'note': 'Positions each cap at ~45° for pick-up.', 'sort_order': 3},
    {'code': 'F', 'name': 'Transfer device', 'note': '"Pick and place" system moving the cap under the capping head.', 'sort_order': 4},
    {'code': 'G', 'name': 'Closure gripper', 'note': 'Mechanical gripper that takes and applies the cap.', 'sort_order': 5},
    {'code': 'D', 'name': 'Star-wheel', 'note': 'Rotates containers into position under the capping head.', 'sort_order': 6},
    {'code': 'E', 'name': 'Capping head', 'note': 'Follows a cam profile to screw the cap onto the container.', 'sort_order': 7},
]


class Command(BaseCommand):
    help = 'Seed a demo machine for a user with a company assignment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='demo',
            help='Username or user_id that belongs to a company (default: demo)',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        user = User.objects.filter(username=username).first() or User.objects.filter(user_id=username).first()
        if user is None:
            raise CommandError(
                f'User "{username}" not found. Run initiliaze_database.py or create a user first.'
            )
        if user.company_id is None:
            company, _ = Company.objects.get_or_create(
                company_id='CMP-DEMO',
                defaults={
                    'company_name': 'Demo Company',
                    'country': 'Italy',
                    'sector': 'Beverage',
                    'city': 'Novara',
                    'currency': 'EUR',
                    'locale': 'it-IT',
                },
            )
            user.company = company
            user.save(update_fields=['company'])

        machine_model, _ = MachineModel.objects.get_or_create(
            model_id='MDL-DEMO',
            defaults={
                'model_code': 'CLOSYS EAGLE VP',
                'description': 'Single-head automatic turret for pre-threaded plastic screw caps',
                'nominal_heads': 1,
                'container_type': 'PET bottles',
                'cap_type': 'Pre-threaded plastic screw cap',
                'industry_segment': 'Beverage',
            },
        )

        machine, created = Machine.objects.update_or_create(
            serial_number='A3279',
            defaults={
                'machine_id': 'MCH-DEMO',
                'company': user.company,
                'model': machine_model,
                'delivery_date': date(2014, 1, 1),
                'plant_location': 'Demo Plant - Line 1',
                'configuration_profile': 'Demo single-head turret / 3000 bph',
                'plc_family': 'SIEMENS-SIMATIC-S7',
                'software_version': '2.3.1',
            },
        )

        MachineUnit.objects.filter(machine=machine).delete()
        MachineUnit.objects.bulk_create([
            MachineUnit(machine=machine, **unit) for unit in A3279_UNITS
        ])

        verb = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{verb} machine A3279 for user {user.username}'))
