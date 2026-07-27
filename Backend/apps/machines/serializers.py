from .models import Machine, MachineUnit


def machine_to_dict(machine: Machine) -> dict:
    """Serialize a Machine into the shape expected by the React machine view."""
    return {
        'id': machine.pk,
        'serialNumber': machine.serial_number,
        'qrToken': machine.qr_token,
        'model': machine.model,
        'fullModel': machine.full_model,
        'manufacturingYear': machine.manufacturing_year,
        'manufacturer': machine.manufacturer,
        'site': machine.site,
        'description': machine.description,
        'manualRevision': machine.manual_revision,
        'manualDate': machine.manual_date,
        'manualUrl': machine.manual_url,
        'identification': {
            'machineType': machine.machine_type,
            'pitchDiameter': machine.pitch_diameter,
            'heads': machine.heads,
            'rotation': machine.rotation,
        },
        'technicalData': {
            'weight': {
                'value': machine.weight_value,
                'unit': machine.weight_unit,
            },
            'productiveCapacity': {
                'value': machine.productive_capacity_value,
                'unit': machine.productive_capacity_unit,
            },
            'electrical': {
                'mainSupply': machine.electrical_main_supply,
                'auxiliarySupply': machine.electrical_auxiliary_supply,
                'totalInstalledPower': machine.electrical_total_installed_power,
                'breakdown': machine.electrical_breakdown or [],
            },
            'pneumatic': {
                'sterileAirCapacity': machine.pneumatic_sterile_air_capacity,
                'minPressure': machine.pneumatic_min_pressure,
                'maxPressure': machine.pneumatic_max_pressure,
            },
        },
        'operatingConditions': {
            'temperature': machine.operating_temperature,
            'environment': machine.operating_environment,
            'noise': machine.operating_noise,
        },
        'certifications': machine.certifications or [],
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
        'id': machine.pk,
        'serialNumber': machine.serial_number,
        'model': machine.model,
        'fullModel': machine.full_model,
        'manufacturingYear': machine.manufacturing_year,
    }
