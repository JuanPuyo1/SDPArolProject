export type OrderLine = {
  orderLineId: string
  fulfillmentStatus: string
}

export type Order = {
  orderId: string
  quoteId: string
  companyId: string
  orderStatus: string
  orderDate: string
  expectedDeliveryDate: string
  shipmentStatus: string
  currency: string
  notes: string
  lines: OrderLine[]
}
