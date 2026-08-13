export type MachineUnit = {
  code: string
  name: string
  note: string
}

export type MachineModelInfo = {
  modelId: string
  modelCode: string
  description: string
  primitiveDiameter: number | null
  nominalHeads: number
  containerType: string
  capType: string
  industrySegment: string
  notes: string
}

export type CompanyInfo = {
  companyId: string
  companyName: string
  country: string
  sector: string
  city: string
  currency: string
  locale: string
}

export type Machine = {
  machineId: string
  serialNumber: string
  deliveryDate: string
  plantLocation: string
  configurationProfile: string
  plcFamily: string
  softwareVersion: string | null
  manualUrl: string | null
  model: MachineModelInfo
  company: CompanyInfo
  mainUnits: MachineUnit[]
}

export type MachineSummary = {
  machineId: string
  serialNumber: string
  modelCode: string
  deliveryDate: string
  plantLocation: string
  industrySegment: string
}
