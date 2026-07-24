// Static machine record, sourced from the A3279 use & maintenance manual.
// In the full platform this would come from the ERP/CRM via the Orders & Docs agent (see MCP Gateway).
export const machine = {
  model: 'CLOSYS EAGLE VP',
  fullModel: 'M - CLOSYS EAGLE VP',
  serialNumber: 'A3279',
  manufacturingYear: 2014,
  manufacturer: 'AROL S.p.A.',
  site: 'Canelli (AT), Italy',
  manualRevision: '01',
  manualDate: '06/2014',
  description:
    'The CLOSYS EAGLE VP is a single-head capping machine that applies pre-threaded (screw) caps to rigid preformed containers. Caps arriving from the caps sorter are driven by a caps chute to the distribution head, picked up and transferred under the capping head, then applied to containers by screwing as the star-wheel carries them through on the transfer belt.',
  identification: {
    machineType: 'Capping machine (screw caps)',
    pitchDiameter: '550 mm',
    heads: 1,
    rotation: 'Clockwise',
  },
  technicalData: {
    weight: { value: '350', unit: 'kg' },
    productiveCapacity: { value: '1,800', unit: 'pcs/h' },
    electrical: {
      mainSupply: '575 V ~ / 60 Hz',
      auxiliarySupply: '24 V =',
      totalInstalledPower: '2.24 kW',
      breakdown: [
        { label: 'Electric board', value: '0.40 kW' },
        { label: 'Machine rotation main motor', value: '1.10 kW' },
        { label: 'Caps sorter motor', value: '0.37 kW' },
        { label: 'Head rotation motor', value: '0.37 kW' },
      ],
    },
    pneumatic: {
      sterileAirCapacity: '~400 Nl/min',
      minPressure: '6 bar',
      maxPressure: '8 bar',
    },
  },
  operatingConditions: {
    temperature: '5 °C to 40 °C',
    environment: 'Ventilated, well-lit closed environment. Not suitable for explosive atmospheres.',
    noise: 'Below 80 dB(A) Leq at nominal production (measured 74-79 dB(A) across 4 points, ISO 4871).',
  },
  certifications: ['CE', 'Directive 2006/42/EC (Machinery)', 'Directive 2004/108/EC (EMC)'],
  mainUnits: [
    { code: 'A', name: 'Caps sorter', note: 'Centrifugal sorter feeding oriented caps into the chute.' },
    { code: 'B', name: 'Caps chute', note: 'Drives caps from the sorter to the distribution head.' },
    { code: 'C', name: 'Distribution head', note: 'Positions each cap at ~45° for pick-up.' },
    { code: 'F', name: 'Transfer device', note: '"Pick and place" system moving the cap under the capping head.' },
    { code: 'G', name: 'Closure gripper', note: 'Mechanical gripper that takes and applies the cap.' },
    { code: 'D', name: 'Star-wheel', note: 'Rotates containers into position under the capping head.' },
    { code: 'E', name: 'Capping head', note: 'Follows a cam profile to screw the cap onto the container.' },
  ],
  manualUrl: '/manual/A3279-use-and-maintenance.pdf',
}

export type Machine = typeof machine
