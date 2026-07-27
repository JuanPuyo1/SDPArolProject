export type MachineUnit = {
  code: string
  name: string
  note: string
}

export type Machine = {
  id: number
  serialNumber: string
  qrToken?: string
  model: string
  fullModel: string
  manufacturingYear: number
  manufacturer: string
  site: string
  description: string
  manualRevision: string
  manualDate: string
  manualUrl: string
  identification: {
    machineType: string
    pitchDiameter: string
    heads: number
    rotation: string
  }
  technicalData: {
    weight: { value: string; unit: string }
    productiveCapacity: { value: string; unit: string }
    electrical: {
      mainSupply: string
      auxiliarySupply: string
      totalInstalledPower: string
      breakdown: { label: string; value: string }[]
    }
    pneumatic: {
      sterileAirCapacity: string
      minPressure: string
      maxPressure: string
    }
  }
  operatingConditions: {
    temperature: string
    environment: string
    noise: string
  }
  certifications: string[]
  mainUnits: MachineUnit[]
}

export type MachineSummary = {
  id: number
  serialNumber: string
  model: string
  fullModel: string
  manufacturingYear: number
}
