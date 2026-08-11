from .manuals import resolve_manual_url
from .models import Machine, MachineUnit


def _machine_model_to_dict(model) -> dict:
    return {
        'modelId': model.model_id,
        'modelCode': model.model_code,
        'description': model.description,
        'primitiveDiameter': (
            float(model.primitive_diameter)
            if model.primitive_diameter is not None
            else None
        ),
        'nominalHeads': model.nominal_heads,
        'containerType': model.container_type,
        'capType': model.cap_type,
        'industrySegment': model.industry_segment,
        'notes': model.notes,
    }


def _company_to_dict(company) -> dict:
    return {
        'companyId': company.company_id,
        'companyName': company.company_name,
        'country': company.country,
        'sector': company.sector,
        'city': company.city,
        'currency': company.currency,
        'locale': company.locale,
    }


def machine_to_dict(machine: Machine) -> dict:
    """Serialize a fleet machine with related catalog and company data."""
    return {
        'machineId': machine.machine_id,
        'serialNumber': machine.serial_number,
        'deliveryDate': machine.delivery_date.isoformat(),
        'plantLocation': machine.plant_location,
        'configurationProfile': machine.configuration_profile,
        'plcFamily': machine.plc_family,
        'softwareVersion': machine.software_version or None,
        'manualUrl': resolve_manual_url(machine.serial_number),
        'model': _machine_model_to_dict(machine.model),
        'company': _company_to_dict(machine.company),
        'mainUnits': [
            {
                'code': unit.code,
                'name': unit.name,
                'note': unit.note,
            }
            for unit in machine.main_units.all()
        ],
    }


def machine_summary_to_dict(machine: Machine) -> dict:
    return {
        'machineId': machine.machine_id,
        'serialNumber': machine.serial_number,
        'modelCode': machine.model.model_code,
        'deliveryDate': machine.delivery_date.isoformat(),
        'plantLocation': machine.plant_location,
        'industrySegment': machine.model.industry_segment,
    }
