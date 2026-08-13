export type MaintenanceTicket = {
  ticketId: string
  machineId: string
  serialNumber: string
  plantLocation: string
  alarmId: string | null
  ticketType: string
  ticketStatus: string
  priority: string
  createdDate: string
  ownerRole: string
}
