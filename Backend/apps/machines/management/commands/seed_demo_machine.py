"""
Seed the CLOSYS EAGLE VP (A3279) machine record for a given user.

Usage:
  python manage.py seed_demo_machine
  python manage.py seed_demo_machine --username demo
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.machines.models import Machine, MachineUnit

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
    help = 'Seed the A3279 CLOSYS EAGLE VP machine for a demo user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='demo',
            help='Username that will own the seeded machine (default: demo)',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(
                f'User "{username}" not found. Create it first '
                f'(e.g. createsuperuser or the demo login user).'
            ) from exc

        machine, created = Machine.objects.update_or_create(
            serial_number='A3279',
            defaults={
                'owner': user,
                'qr_token': 'A3279-qr',
                'model': 'CLOSYS EAGLE VP',
                'full_model': 'M - CLOSYS EAGLE VP',
                'manufacturing_year': 2014,
                'manufacturer': 'AROL S.p.A.',
                'site': 'Canelli (AT), Italy',
                'description': (
                    'The CLOSYS EAGLE VP is a single-head capping machine that applies '
                    'pre-threaded (screw) caps to rigid preformed containers. Caps arriving '
                    'from the caps sorter are driven by a caps chute to the distribution head, '
                    'picked up and transferred under the capping head, then applied to containers '
                    'by screwing as the star-wheel carries them through on the transfer belt.'
                ),
                'machine_type': 'Capping machine (screw caps)',
                'pitch_diameter': '550 mm',
                'heads': 1,
                'rotation': 'Clockwise',
                'manual_revision': '01',
                'manual_date': '06/2014',
                'manual_url': '/manual/A3279-use-and-maintenance.pdf',
                'weight_value': '350',
                'weight_unit': 'kg',
                'productive_capacity_value': '1,800',
                'productive_capacity_unit': 'pcs/h',
                'electrical_main_supply': '575 V ~ / 60 Hz',
                'electrical_auxiliary_supply': '24 V =',
                'electrical_total_installed_power': '2.24 kW',
                'electrical_breakdown': [
                    {'label': 'Electric board', 'value': '0.40 kW'},
                    {'label': 'Machine rotation main motor', 'value': '1.10 kW'},
                    {'label': 'Caps sorter motor', 'value': '0.37 kW'},
                    {'label': 'Head rotation motor', 'value': '0.37 kW'},
                ],
                'pneumatic_sterile_air_capacity': '~400 Nl/min',
                'pneumatic_min_pressure': '6 bar',
                'pneumatic_max_pressure': '8 bar',
                'operating_temperature': '5 °C to 40 °C',
                'operating_environment': (
                    'Ventilated, well-lit closed environment. '
                    'Not suitable for explosive atmospheres.'
                ),
                'operating_noise': (
                    'Below 80 dB(A) Leq at nominal production '
                    '(measured 74-79 dB(A) across 4 points, ISO 4871).'
                ),
                'certifications': [
                    'CE',
                    'Directive 2006/42/EC (Machinery)',
                    'Directive 2004/108/EC (EMC)',
                ],
            },
        )

        machine.main_units.all().delete()
        MachineUnit.objects.bulk_create([
            MachineUnit(machine=machine, **unit) for unit in A3279_UNITS
        ])

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} machine A3279 for user "{username}" '
            f'({machine.main_units.count()} units).'
        ))
