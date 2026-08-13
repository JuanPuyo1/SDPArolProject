"""
Load the AROL Q2 synthetic fleet dataset from Excel into the database.

Usage (from Backend/):
  ..\\.venv\\Scripts\\python.exe initiliaze_database.py
  ..\\.venv\\Scripts\\python.exe initiliaze_database.py --excel static/AROL_Q2_synthetic_fleet_dataset.xlsx
  ..\\.venv\\Scripts\\python.exe initiliaze_database.py --flush
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from pathlib import Path

import django
import pandas as pd
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_EXCEL = BASE_DIR / 'static' / 'AROL_Q2_synthetic_fleet_dataset.xlsx'
DEFAULT_PASSWORD = 'changeme'


def _setup_django() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    sys.path.insert(0, str(BASE_DIR))
    django.setup()


def _parse_date(value) -> date:
    if pd.isna(value):
        raise ValueError('date value is required')
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.to_datetime(value).date()


def _parse_datetime(value) -> datetime:
    if pd.isna(value):
        raise ValueError('datetime value is required')
    dt = pd.to_datetime(value).to_pydatetime()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, datetime_timezone.utc)
    return dt


def _optional_str(value) -> str:
    if pd.isna(value):
        return ''
    return str(value).strip()


def _optional_decimal(value) -> Decimal | None:
    if pd.isna(value):
        return None
    return Decimal(str(value))


def _require_str(value, field: str) -> str:
    text = _optional_str(value)
    if not text:
        raise ValueError(f'{field} is required')
    return text


def load_excel(excel_path: Path) -> dict[str, pd.DataFrame]:
    xl = pd.ExcelFile(excel_path)
    return {sheet: pd.read_excel(xl, sheet_name=sheet) for sheet in xl.sheet_names}


@transaction.atomic
def import_dataset(excel_path: Path, *, flush: bool = False) -> None:
    from apps.core.models import Company
    from apps.machines.models import (
        Alarm,
        Machine,
        MachineModel,
        MaintenanceTicket,
        TelemetrySnapshot,
    )
    from apps.quotes.models import Order, OrderLine, Quote, QuoteLine, QuoteRevision

    User = get_user_model()
    sheets = load_excel(excel_path)

    if flush:
        MaintenanceTicket.objects.all().delete()
        Alarm.objects.all().delete()
        TelemetrySnapshot.objects.all().delete()
        OrderLine.objects.all().delete()
        Order.objects.all().delete()
        QuoteLine.objects.all().delete()
        QuoteRevision.objects.all().delete()
        Quote.objects.all().delete()
        Machine.objects.all().delete()
        MachineModel.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Company.objects.all().delete()

    companies_df = sheets['Companies']
    for row in companies_df.itertuples(index=False):
        Company.objects.update_or_create(
            company_id=row.companyId,
            defaults={
                'company_name': row.companyName,
                'country': row.country,
                'sector': row.sector,
                'city': row.city,
                'currency': row.currency,
                'locale': row.locale,
            },
        )
    print(f'Companies: {Company.objects.count()}')

    users_df = sheets['Users']
    for row in users_df.itertuples(index=False):
        user, created = User.objects.update_or_create(
            user_id=row.userId,
            defaults={
                'username': row.userId,
                'email': row.email,
                'first_name': row.firstName,
                'last_name': row.lastName,
                'company_id': row.companyId,
                'job_title': row.jobTitle,
                'visibility': row.visibility,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(DEFAULT_PASSWORD)
            user.save(update_fields=['password'])
    print(f'Users: {User.objects.count()} (default password: {DEFAULT_PASSWORD!r})')

    models_df = sheets['MachineModels']
    for row in models_df.itertuples(index=False):
        MachineModel.objects.update_or_create(
            model_id=row.modelId,
            defaults={
                'model_code': row.modelCode,
                'description': row.description,
                'primitive_diameter': _optional_decimal(row.primitiveDiameter),
                'nominal_heads': int(row.nominalHeads),
                'container_type': row.containerType,
                'cap_type': row.capType,
                'industry_segment': row.industrySegment,
                'notes': _optional_str(row.notes),
            },
        )
    print(f'Machine models: {MachineModel.objects.count()}')

    machines_df = sheets['Machines']
    for row in machines_df.itertuples(index=False):
        Machine.objects.update_or_create(
            machine_id=row.machineId,
            defaults={
                'company_id': row.companyId,
                'model_id': row.modelId,
                'serial_number': str(row.serialNumber),
                'delivery_date': _parse_date(row.deliveryDate),
                'plant_location': row.plantLocation,
                'configuration_profile': row.configurationProfile,
                'plc_family': row.plcFamily,
                'software_version': _optional_str(row.softwareVersion),
            },
        )
    print(f'Machines: {Machine.objects.count()}')

    quotes_df = sheets['Quotes']
    for row in quotes_df.itertuples(index=False):
        Quote.objects.update_or_create(
            quote_id=row.quoteId,
            defaults={
                'company_id': row.companyId,
                'currency': row.currency,
                'created_at': _parse_date(row.createdAt),
                'valid_until': _parse_date(row.validUntil),
                'description': row.description,
            },
        )
    print(f'Quotes: {Quote.objects.count()}')

    revisions_df = sheets['QuoteRevisions']
    for row in revisions_df.itertuples(index=False):
        QuoteRevision.objects.update_or_create(
            quote_revision_id=row.quoteRevisionId,
            defaults={
                'quote_id': row.quoteId,
                'revision_number': int(row.revisionNumber),
                'revision_status': row.revisionStatus,
                'issued_at': _parse_date(row.issuedAt),
                'discount_rate': Decimal(str(row.discountRate)),
                'change_summary': row.changeSummary,
            },
        )
    print(f'Quote revisions: {QuoteRevision.objects.count()}')

    quote_lines_df = sheets['QuoteLines']
    for row in quote_lines_df.itertuples(index=False):
        machine_id = _optional_str(row.machineId) or None
        QuoteLine.objects.update_or_create(
            quote_line_id=row.quoteLineId,
            defaults={
                'quote_revision_id': row.quoteRevisionId,
                'machine_id': machine_id,
                'price': Decimal(str(row.price)),
                'description': row.description,
            },
        )
    print(f'Quote lines: {QuoteLine.objects.count()}')

    orders_df = sheets['Orders']
    for row in orders_df.itertuples(index=False):
        Order.objects.update_or_create(
            order_id=row.orderId,
            defaults={
                'quote_id': row.quoteId,
                'company_id': row.companyId,
                'order_status': row.orderStatus,
                'order_date': _parse_date(row.orderDate),
                'expected_delivery_date': _parse_date(row.expectedDeliveryDate),
                'shipment_status': row.shipmentStatus,
                'currency': row.currency,
                'notes': _optional_str(row.notes),
            },
        )
    print(f'Orders: {Order.objects.count()}')

    order_lines_df = sheets['OrderLines']
    for row in order_lines_df.itertuples(index=False):
        OrderLine.objects.update_or_create(
            order_line_id=row.orderLineId,
            defaults={
                'order_id': row.orderId,
                'fulfillment_status': row.fulfillmentStatus,
            },
        )
    print(f'Order lines: {OrderLine.objects.count()}')

    telemetry_df = sheets['TelemetrySnapshots']
    telemetry_batch: list[TelemetrySnapshot] = []
    batch_size = 500
    for row in telemetry_df.itertuples(index=False):
        telemetry_batch.append(
            TelemetrySnapshot(
                telemetry_id=row.telemetryId,
                machine_id=row.machineId,
                timestamp=_parse_datetime(row.timestamp),
                operational_status=row.operationalStatus,
                production_rate_bph=int(row.productionRateBph),
                uptime_percentage=Decimal(str(row.uptimePercentage)),
                alarm_count=int(row.alarmCount),
                temperature_c=Decimal(str(row.temperatureC)),
                energy_kwh=Decimal(str(row.energyKwh)),
                health_note=row.healthNote,
            )
        )
        if len(telemetry_batch) >= batch_size:
            TelemetrySnapshot.objects.bulk_create(
                telemetry_batch,
                update_conflicts=True,
                unique_fields=['telemetry_id'],
                update_fields=[
                    'machine_id',
                    'timestamp',
                    'operational_status',
                    'production_rate_bph',
                    'uptime_percentage',
                    'alarm_count',
                    'temperature_c',
                    'energy_kwh',
                    'health_note',
                ],
            )
            telemetry_batch.clear()
    if telemetry_batch:
        TelemetrySnapshot.objects.bulk_create(
            telemetry_batch,
            update_conflicts=True,
            unique_fields=['telemetry_id'],
            update_fields=[
                'machine_id',
                'timestamp',
                'operational_status',
                'production_rate_bph',
                'uptime_percentage',
                'alarm_count',
                'temperature_c',
                'energy_kwh',
                'health_note',
            ],
        )
    print(f'Telemetry snapshots: {TelemetrySnapshot.objects.count()}')

    alarms_df = sheets['Alarms']
    for row in alarms_df.itertuples(index=False):
        Alarm.objects.update_or_create(
            alarm_id=row.alarmId,
            defaults={
                'machine_id': row.machineId,
                'timestamp': _parse_datetime(row.timestamp),
                'alarm_code': row.alarmCode,
                'severity': row.severity,
                'alarm_status': row.alarmStatus,
            },
        )
    print(f'Alarms: {Alarm.objects.count()}')

    tickets_df = sheets['MaintenanceTickets']
    for row in tickets_df.itertuples(index=False):
        alarm_id = _optional_str(row.alarmId) or None
        MaintenanceTicket.objects.update_or_create(
            ticket_id=row.ticketId,
            defaults={
                'machine_id': row.machineId,
                'alarm_id': alarm_id,
                'ticket_type': row.ticketType,
                'ticket_status': row.ticketStatus,
                'priority': row.priority,
                'created_date': _parse_date(row.createdDate),
                'owner_role': row.ownerRole,
            },
        )
    print(f'Maintenance tickets: {MaintenanceTicket.objects.count()}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Import AROL Q2 synthetic fleet dataset.')
    parser.add_argument(
        '--excel',
        type=Path,
        default=DEFAULT_EXCEL,
        help=f'Path to the Excel workbook (default: {DEFAULT_EXCEL.name})',
    )
    parser.add_argument(
        '--flush',
        action='store_true',
        help='Delete existing fleet data before import (keeps superusers).',
    )
    args = parser.parse_args()

    if not args.excel.exists():
        raise SystemExit(f'Excel file not found: {args.excel}')

    _setup_django()
    import_dataset(args.excel, flush=args.flush)
    print('Database initialization complete.')


if __name__ == '__main__':
    main()
