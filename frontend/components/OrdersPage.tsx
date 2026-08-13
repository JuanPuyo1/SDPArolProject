import { useClientTable, uniqueValues } from '../src/hooks/useClientTable'
import { useOrders } from '../src/hooks/useOrders'
import type { Order } from '../src/types/order'
import './DataTable.css'

function statusClass(value: string): string {
  return `tag-pill tag-pill--${value.toLowerCase().replace(/\s+/g, '-')}`
}

export default function OrdersPage() {
  const { orders, loading, error } = useOrders()
  const table = useClientTable<Order>({
    rows: orders,
    searchKeys: ['orderId', 'quoteId', 'notes', 'currency'],
    defaultSortKey: 'orderDate',
    defaultSortDirection: 'desc',
  })

  const orderStatuses = uniqueValues(orders, 'orderStatus')
  const shipmentStatuses = uniqueValues(orders, 'shipmentStatus')

  return (
    <div className="table-page">
      <header>
        <div className="table-page__eyebrow">Commercial</div>
        <h1 className="table-page__title">Orders</h1>
        <p className="table-page__subtitle">
          Confirmed orders for your company. Filter and sort update the table instantly.
        </p>
      </header>

      {loading && <p className="table-page__status">Loading orders…</p>}
      {error && <p className="table-page__status table-page__status--error">{error}</p>}

      {!loading && !error && (
        <>
          <div className="table-toolbar">
            <div className="table-toolbar__field table-toolbar__field--search">
              <label htmlFor="orders-search">Search</label>
              <input
                id="orders-search"
                type="search"
                placeholder="Order ID, quote, notes…"
                value={table.search}
                onChange={(event) => table.setSearch(event.target.value)}
              />
            </div>
            <div className="table-toolbar__field">
              <label htmlFor="orders-status">Order status</label>
              <select
                id="orders-status"
                value={table.filters.orderStatus ?? ''}
                onChange={(event) => table.setFilter('orderStatus', event.target.value)}
              >
                <option value="">All</option>
                {orderStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div className="table-toolbar__field">
              <label htmlFor="orders-shipment">Shipment status</label>
              <select
                id="orders-shipment"
                value={table.filters.shipmentStatus ?? ''}
                onChange={(event) => table.setFilter('shipmentStatus', event.target.value)}
              >
                <option value="">All</option>
                {shipmentStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div className="table-toolbar__actions">
              <button type="button" className="btn btn--ghost" onClick={table.clearFilters}>
                Clear
              </button>
            </div>
            <div className="table-toolbar__meta">
              {table.filteredRows.length} of {orders.length}
            </div>
          </div>

          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <SortHeader
                    label="Order"
                    active={table.sortKey === 'orderId'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('orderId')}
                  />
                  <SortHeader
                    label="Quote"
                    active={table.sortKey === 'quoteId'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('quoteId')}
                  />
                  <SortHeader
                    label="Status"
                    active={table.sortKey === 'orderStatus'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('orderStatus')}
                  />
                  <SortHeader
                    label="Shipment"
                    active={table.sortKey === 'shipmentStatus'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('shipmentStatus')}
                  />
                  <SortHeader
                    label="Order date"
                    active={table.sortKey === 'orderDate'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('orderDate')}
                  />
                  <SortHeader
                    label="Expected delivery"
                    active={table.sortKey === 'expectedDeliveryDate'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('expectedDeliveryDate')}
                  />
                  <th>Currency</th>
                  <th>Lines</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {table.filteredRows.length === 0 ? (
                  <tr>
                    <td className="data-table__empty" colSpan={9}>
                      No orders match the current filters.
                    </td>
                  </tr>
                ) : (
                  table.filteredRows.map((order) => (
                    <tr key={order.orderId}>
                      <td>{order.orderId}</td>
                      <td>{order.quoteId}</td>
                      <td>
                        <span className={statusClass(order.orderStatus)}>
                          {order.orderStatus}
                        </span>
                      </td>
                      <td>
                        <span className={statusClass(order.shipmentStatus)}>
                          {order.shipmentStatus}
                        </span>
                      </td>
                      <td>{order.orderDate}</td>
                      <td>{order.expectedDeliveryDate}</td>
                      <td>{order.currency}</td>
                      <td>{order.lines.length}</td>
                      <td>{order.notes || '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function SortHeader({
  label,
  active,
  direction,
  onClick,
}: {
  label: string
  active: boolean
  direction: 'asc' | 'desc'
  onClick: () => void
}) {
  return (
    <th>
      <button
        type="button"
        className={
          active ? 'data-table__sort data-table__sort--active' : 'data-table__sort'
        }
        onClick={onClick}
      >
        {label}
        {active ? (direction === 'asc' ? ' ↑' : ' ↓') : ''}
      </button>
    </th>
  )
}
