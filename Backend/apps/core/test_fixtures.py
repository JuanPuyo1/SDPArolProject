"""Shared AROL-spec fleet fixtures for Django tests.

Mirrors README_AROL.md: two tenants, three visibility roles, a company with
users but no machines, empty optional FKs, quote revisions, and operational
rows (telemetry / alarms / tickets).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Company
from apps.machines.models import (
    Alarm,
    Machine,
    MachineModel,
    MaintenanceTicket,
    TelemetrySnapshot,
)
from apps.quotes.models import Order, OrderLine, Quote, QuoteLine, QuoteRevision

PASSWORD = "test-pass"


@dataclass
class SpecFleet:
    acme: Company
    other: Company
    empty: Company
    full_user: object
    technician: object
    commercial: object
    other_user: object
    empty_user: object
    model: MachineModel
    model_no_diameter: MachineModel
    machine: Machine
    machine2: Machine
    foreign_machine: Machine
    open_alarm: Alarm
    resolved_alarm: Alarm
    ticket_from_alarm: MaintenanceTicket
    ticket_without_alarm: MaintenanceTicket
    quote: Quote
    approved_revision: QuoteRevision
    superseded_revision: QuoteRevision
    rejected_quote: Quote
    orphan_quote: Quote
    order: Order


def seed_spec_fleet() -> SpecFleet:
    User = get_user_model()

    acme = Company.objects.create(
        company_id="CMP-ACME",
        company_name="Acme Bottling",
        country="Italy",
        sector="Beverage",
        city="Novara",
        currency="EUR",
        locale="it-IT",
    )
    other = Company.objects.create(
        company_id="CMP-OTHER",
        company_name="Other Spirits",
        country="France",
        sector="Spirits",
        city="Saintes",
        currency="EUR",
        locale="fr-FR",
    )
    empty = Company.objects.create(
        company_id="CMP-EMPTY",
        company_name="Empty Holdings",
        country="Spain",
        sector="Food",
        city="Valencia",
        currency="EUR",
        locale="es-ES",
    )

    full_user = User.objects.create_user(
        username="acme_full",
        password=PASSWORD,
        user_id="USR-ACME-FULL",
        email="full@acme.test",
        first_name="Ada",
        last_name="Full",
        company=acme,
        job_title="Plant Manager",
        visibility="full",
    )
    technician = User.objects.create_user(
        username="acme_tech",
        password=PASSWORD,
        user_id="USR-ACME-TECH",
        email="tech@acme.test",
        first_name="Theo",
        last_name="Tech",
        company=acme,
        job_title="Maintenance Man",
        visibility="technician",
    )
    commercial = User.objects.create_user(
        username="acme_comm",
        password=PASSWORD,
        user_id="USR-ACME-COMM",
        email="comm@acme.test",
        first_name="Cara",
        last_name="Comm",
        company=acme,
        job_title="Buyer",
        visibility="commercial",
    )
    other_user = User.objects.create_user(
        username="other_full",
        password=PASSWORD,
        user_id="USR-OTHER-FULL",
        email="full@other.test",
        first_name="Omar",
        last_name="Other",
        company=other,
        visibility="full",
    )
    empty_user = User.objects.create_user(
        username="empty_user",
        password=PASSWORD,
        user_id="USR-EMPTY",
        email="user@empty.test",
        first_name="Eva",
        last_name="Empty",
        company=empty,
        visibility="full",
    )

    model = MachineModel.objects.create(
        model_id="MDL-EAGLE",
        model_code="CLOSYS EAGLE VP",
        description="Rotary capper",
        primitive_diameter=Decimal("180.0"),
        nominal_heads=8,
        container_type="PET bottles",
        cap_type="Plastic screw cap",
        industry_segment="Beverage",
        notes="Standard beverage capper",
    )
    model_no_diameter = MachineModel.objects.create(
        model_id="MDL-NODIAM",
        model_code="HARDWIRED BENCH",
        description="Model with no declared pitch diameter",
        primitive_diameter=None,
        nominal_heads=1,
        container_type="Jars",
        cap_type="Twist-off",
        industry_segment="Food",
    )

    machine = Machine.objects.create(
        machine_id="MCH-0004",
        company=acme,
        model=model,
        serial_number="17478",
        delivery_date=date(2019, 7, 22),
        plant_location="Novara Line 1",
        configuration_profile=(
            "Nominal production rate 24000 BPH; supply 400V; "
            "magnetic capping heads."
        ),
        plc_family="SIEMENS-SIMATIC-S7",
        software_version="V4.2",
    )
    machine2 = Machine.objects.create(
        machine_id="MCH-TEST1",
        company=acme,
        model=model_no_diameter,
        serial_number="A3279",
        delivery_date=date(2014, 1, 1),
        plant_location="Novara Line 2",
        configuration_profile="Nominal production rate 6000 BPH; 230V.",
        plc_family="HARDWIRED-CONTROL-PANEL",
    )
    foreign_machine = Machine.objects.create(
        machine_id="MCH-FOREIGN",
        company=other,
        model=model,
        serial_number="99999",
        delivery_date=date(2018, 1, 1),
        plant_location="Saintes Line A",
        configuration_profile="Foreign config",
        plc_family="LINE-PLC-INTEGRATED",
    )

    now = timezone.now()
    hour = now.replace(minute=0, second=0, microsecond=0)

    TelemetrySnapshot.objects.create(
        telemetry_id="TEL-RUN",
        machine=machine,
        timestamp=hour,
        operational_status="Running",
        production_rate_bph=18000,
        uptime_percentage=Decimal("92.5"),
        alarm_count=1,
        temperature_c=Decimal("41.0"),
        energy_kwh=Decimal("12.50"),
        health_note="Normal production",
    )
    TelemetrySnapshot.objects.create(
        telemetry_id="TEL-IDLE",
        machine=machine,
        timestamp=hour - timedelta(hours=1),
        operational_status="Idle",
        production_rate_bph=0,
        uptime_percentage=Decimal("0.0"),
        alarm_count=0,
        temperature_c=Decimal("28.0"),
        energy_kwh=Decimal("1.10"),
        health_note="Not producing",
    )

    open_alarm = Alarm.objects.create(
        alarm_id="ALM-OPEN",
        machine=machine,
        timestamp=hour,
        alarm_code="AL017_LOW_AIR_PRESSURE",
        severity="High",
        alarm_status="Open",
    )
    resolved_alarm = Alarm.objects.create(
        alarm_id="ALM-RES",
        machine=machine,
        timestamp=hour - timedelta(hours=2),
        alarm_code="AL001_EMERGENCY_STOP",
        severity="Critical",
        alarm_status="Resolved",
    )
    Alarm.objects.create(
        alarm_id="ALM-FOREIGN",
        machine=foreign_machine,
        timestamp=hour,
        alarm_code="AL017_LOW_AIR_PRESSURE",
        severity="High",
        alarm_status="Open",
    )

    ticket_from_alarm = MaintenanceTicket.objects.create(
        ticket_id="TKT-FROM-ALM",
        machine=machine,
        alarm=open_alarm,
        ticket_type="Remote troubleshooting",
        ticket_status="Open",
        priority="High",
        created_date=date(2026, 8, 1),
        owner_role="AROL Technical Service",
    )
    ticket_without_alarm = MaintenanceTicket.objects.create(
        ticket_id="TKT-NO-ALM",
        machine=machine,
        alarm=None,
        ticket_type="Scheduled maintenance",
        ticket_status="In progress",
        priority="Medium",
        created_date=date(2026, 7, 15),
        owner_role="Plant Maintenance Manager",
    )

    quote = Quote.objects.create(
        quote_id="QUO-SPEC-1",
        company=acme,
        currency="EUR",
        created_at=date(2025, 1, 10),
        valid_until=date(2025, 3, 10),
        description="Capper upgrade pack",
    )
    superseded_revision = QuoteRevision.objects.create(
        quote_revision_id="QREV-1",
        quote=quote,
        revision_number=1,
        revision_status="Superseded",
        issued_at=date(2025, 1, 10),
        discount_rate=Decimal("0.1000"),
        change_summary="Initial offer",
    )
    QuoteLine.objects.create(
        quote_line_id="QL-1A",
        quote_revision=superseded_revision,
        machine=machine,
        price=Decimal("10000.00"),
        description="Base machine (rev 1, already net of 10%)",
    )
    approved_revision = QuoteRevision.objects.create(
        quote_revision_id="QREV-2",
        quote=quote,
        revision_number=2,
        revision_status="Approved",
        issued_at=date(2025, 2, 1),
        discount_rate=Decimal("0.1500"),
        change_summary="Discounted spare pack",
    )
    QuoteLine.objects.create(
        quote_line_id="QL-2A",
        quote_revision=approved_revision,
        machine=machine,
        price=Decimal("8500.00"),
        description="Base machine (rev 2, already net of 15%)",
    )
    QuoteLine.objects.create(
        quote_line_id="QL-2B",
        quote_revision=approved_revision,
        machine=None,
        price=Decimal("500.00"),
        description="Training (no installed machine)",
    )

    rejected_quote = Quote.objects.create(
        quote_id="QUO-REJECT",
        company=acme,
        currency="EUR",
        created_at=date(2024, 6, 1),
        valid_until=date(2024, 7, 1),
        description="Rejected final revision",
    )
    QuoteRevision.objects.create(
        quote_revision_id="QREV-R1",
        quote=rejected_quote,
        revision_number=1,
        revision_status="Approved",
        issued_at=date(2024, 6, 1),
        discount_rate=Decimal("0.0000"),
        change_summary="Original approved offer",
    )
    QuoteLine.objects.create(
        quote_line_id="QL-R1",
        quote_revision_id="QREV-R1",
        machine=machine,
        price=Decimal("1000.00"),
        description="Approved revision lines",
    )
    QuoteRevision.objects.create(
        quote_revision_id="QREV-R2",
        quote=rejected_quote,
        revision_number=2,
        revision_status="Rejected",
        issued_at=date(2024, 6, 20),
        discount_rate=Decimal("0.0000"),
        change_summary="Customer rejected the last revision",
    )
    QuoteLine.objects.create(
        quote_line_id="QL-R2",
        quote_revision_id="QREV-R2",
        machine=machine,
        price=Decimal("1.00"),
        description="Rejected revision placeholder",
    )

    orphan_quote = Quote.objects.create(
        quote_id="QUO-ORPHAN",
        company=acme,
        currency="EUR",
        created_at=date(2025, 5, 1),
        valid_until=date(2025, 6, 1),
        description="Never became an order",
    )
    QuoteRevision.objects.create(
        quote_revision_id="QREV-O1",
        quote=orphan_quote,
        revision_number=1,
        revision_status="Submitted",
        issued_at=date(2025, 5, 1),
        discount_rate=Decimal("0.0000"),
        change_summary="Waiting for customer",
    )

    Order.objects.create(
        order_id="ORD-REJECT-SRC",
        quote=rejected_quote,
        company=acme,
        order_status="Confirmed",
        order_date=date(2024, 6, 5),
        expected_delivery_date=date(2024, 8, 1),
        shipment_status="In production",
        currency="EUR",
        notes="Should be priced from the Approved revision, not the later Rejected one.",
    )

    order = Order.objects.create(
        order_id="ORD-SPEC-1",
        quote=quote,
        company=acme,
        order_status="Delivered",
        order_date=date(2025, 2, 10),
        expected_delivery_date=date(2025, 4, 1),
        shipment_status="Installed",
        currency="EUR",
        notes="From approved revision",
    )
    OrderLine.objects.create(
        order_line_id="OL-1",
        order=order,
        fulfillment_status="Delivered",
    )

    return SpecFleet(
        acme=acme,
        other=other,
        empty=empty,
        full_user=full_user,
        technician=technician,
        commercial=commercial,
        other_user=other_user,
        empty_user=empty_user,
        model=model,
        model_no_diameter=model_no_diameter,
        machine=machine,
        machine2=machine2,
        foreign_machine=foreign_machine,
        open_alarm=open_alarm,
        resolved_alarm=resolved_alarm,
        ticket_from_alarm=ticket_from_alarm,
        ticket_without_alarm=ticket_without_alarm,
        quote=quote,
        approved_revision=approved_revision,
        superseded_revision=superseded_revision,
        rejected_quote=rejected_quote,
        orphan_quote=orphan_quote,
        order=order,
    )
