import { useClientTable, uniqueValues } from '../src/hooks/useClientTable'
import { useMaintenanceTickets } from '../src/hooks/useMaintenanceTickets'
import type { MaintenanceTicket } from '../src/types/ticket'
import './DataTable.css'

function statusClass(value: string): string {
  return `tag-pill tag-pill--${value.toLowerCase().replace(/\s+/g, '-')}`
}

export default function MaintenanceTicketsPage() {
  const { tickets, loading, error } = useMaintenanceTickets()
  const table = useClientTable<MaintenanceTicket>({
    rows: tickets,
    searchKeys: ['ticketId', 'serialNumber', 'plantLocation', 'ownerRole', 'alarmId'],
    defaultSortKey: 'createdDate',
    defaultSortDirection: 'desc',
  })

  const ticketStatuses = uniqueValues(tickets, 'ticketStatus')
  const priorities = uniqueValues(tickets, 'priority')
  const ticketTypes = uniqueValues(tickets, 'ticketType')

  return (
    <div className="table-page">
      <header>
        <div className="table-page__eyebrow">Service</div>
        <h1 className="table-page__title">Maintenance tickets</h1>
        <p className="table-page__subtitle">
          Current service tickets for your machines. Filter and sort update the table
          instantly.
        </p>
      </header>

      {loading && <p className="table-page__status">Loading tickets…</p>}
      {error && <p className="table-page__status table-page__status--error">{error}</p>}

      {!loading && !error && (
        <>
          <div className="table-toolbar">
            <div className="table-toolbar__field table-toolbar__field--search">
              <label htmlFor="tickets-search">Search</label>
              <input
                id="tickets-search"
                type="search"
                placeholder="Ticket ID, serial, plant…"
                value={table.search}
                onChange={(event) => table.setSearch(event.target.value)}
              />
            </div>
            <div className="table-toolbar__field">
              <label htmlFor="tickets-status">Status</label>
              <select
                id="tickets-status"
                value={table.filters.ticketStatus ?? ''}
                onChange={(event) => table.setFilter('ticketStatus', event.target.value)}
              >
                <option value="">All</option>
                {ticketStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div className="table-toolbar__field">
              <label htmlFor="tickets-priority">Priority</label>
              <select
                id="tickets-priority"
                value={table.filters.priority ?? ''}
                onChange={(event) => table.setFilter('priority', event.target.value)}
              >
                <option value="">All</option>
                {priorities.map((priority) => (
                  <option key={priority} value={priority}>
                    {priority}
                  </option>
                ))}
              </select>
            </div>
            <div className="table-toolbar__field">
              <label htmlFor="tickets-type">Type</label>
              <select
                id="tickets-type"
                value={table.filters.ticketType ?? ''}
                onChange={(event) => table.setFilter('ticketType', event.target.value)}
              >
                <option value="">All</option>
                {ticketTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
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
              {table.filteredRows.length} of {tickets.length}
            </div>
          </div>

          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <SortHeader
                    label="Ticket"
                    active={table.sortKey === 'ticketId'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('ticketId')}
                  />
                  <SortHeader
                    label="Serial"
                    active={table.sortKey === 'serialNumber'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('serialNumber')}
                  />
                  <SortHeader
                    label="Type"
                    active={table.sortKey === 'ticketType'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('ticketType')}
                  />
                  <SortHeader
                    label="Status"
                    active={table.sortKey === 'ticketStatus'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('ticketStatus')}
                  />
                  <SortHeader
                    label="Priority"
                    active={table.sortKey === 'priority'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('priority')}
                  />
                  <SortHeader
                    label="Created"
                    active={table.sortKey === 'createdDate'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('createdDate')}
                  />
                  <SortHeader
                    label="Owner"
                    active={table.sortKey === 'ownerRole'}
                    direction={table.sortDirection}
                    onClick={() => table.toggleSort('ownerRole')}
                  />
                  <th>Plant</th>
                  <th>Alarm</th>
                </tr>
              </thead>
              <tbody>
                {table.filteredRows.length === 0 ? (
                  <tr>
                    <td className="data-table__empty" colSpan={9}>
                      No tickets match the current filters.
                    </td>
                  </tr>
                ) : (
                  table.filteredRows.map((ticket) => (
                    <tr key={ticket.ticketId}>
                      <td>{ticket.ticketId}</td>
                      <td>{ticket.serialNumber}</td>
                      <td>{ticket.ticketType}</td>
                      <td>
                        <span className={statusClass(ticket.ticketStatus)}>
                          {ticket.ticketStatus}
                        </span>
                      </td>
                      <td>
                        <span className={statusClass(ticket.priority)}>
                          {ticket.priority}
                        </span>
                      </td>
                      <td>{ticket.createdDate}</td>
                      <td>{ticket.ownerRole}</td>
                      <td>{ticket.plantLocation}</td>
                      <td>{ticket.alarmId || '—'}</td>
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
