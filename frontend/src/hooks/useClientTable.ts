import { useMemo, useState } from 'react'

export type SortDirection = 'asc' | 'desc'

type UseClientTableOptions<T> = {
  rows: T[]
  searchKeys: (keyof T)[]
  defaultSortKey: keyof T
  defaultSortDirection?: SortDirection
}

function compareValues(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0
  if (a == null) return -1
  if (b == null) return 1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, {
    numeric: true,
    sensitivity: 'base',
  })
}

/**
 * Client-side search / column filters / sort so tables update without a page reload.
 */
export function useClientTable<T extends object>({
  rows,
  searchKeys,
  defaultSortKey,
  defaultSortDirection = 'desc',
}: UseClientTableOptions<T>) {
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState<Partial<Record<keyof T, string>>>({})
  const [sortKey, setSortKey] = useState<keyof T>(defaultSortKey)
  const [sortDirection, setSortDirection] = useState<SortDirection>(defaultSortDirection)

  function setFilter(key: keyof T, value: string) {
    setFilters((prev) => {
      const next = { ...prev }
      if (!value) {
        delete next[key]
      } else {
        next[key] = value
      }
      return next
    })
  }

  function toggleSort(key: keyof T) {
    if (key === sortKey) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(key)
    setSortDirection('asc')
  }

  function clearFilters() {
    setSearch('')
    setFilters({})
  }

  const filteredRows = useMemo(() => {
    const needle = search.trim().toLowerCase()

    const matched = rows.filter((row) => {
      for (const [key, value] of Object.entries(filters) as [keyof T, string][]) {
        if (value && String(row[key] ?? '') !== value) return false
      }

      if (!needle) return true
      return searchKeys.some((key) =>
        String(row[key] ?? '')
          .toLowerCase()
          .includes(needle),
      )
    })

    const sorted = [...matched].sort((a, b) => {
      const result = compareValues(rowValue(a, sortKey), rowValue(b, sortKey))
      return sortDirection === 'asc' ? result : -result
    })

    return sorted
  }, [rows, search, filters, searchKeys, sortKey, sortDirection])

  return {
    search,
    setSearch,
    filters,
    setFilter,
    sortKey,
    sortDirection,
    toggleSort,
    clearFilters,
    filteredRows,
  }
}

function rowValue<T extends object>(row: T, key: keyof T): unknown {
  return row[key]
}

export function uniqueValues<T>(rows: T[], key: keyof T): string[] {
  const values = new Set<string>()
  for (const row of rows) {
    const value = row[key]
    if (value != null && value !== '') values.add(String(value))
  }
  return [...values].sort((a, b) => a.localeCompare(b))
}
