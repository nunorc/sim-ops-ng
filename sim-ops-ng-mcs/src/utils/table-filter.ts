/** Show only the rows (after the header) of table `tableId` with a cell containing input `inputId`'s text. */
export function filterTableRows(inputId: string, tableId: string): void {
  const input = document.getElementById(inputId) as HTMLInputElement | null
  const table = document.getElementById(tableId) as HTMLTableElement | null
  if (!input || !table) return

  const filter = input.value.toUpperCase()
  for (const row of Array.from(table.rows).slice(1)) {
    const found = Array.from(row.cells).some((col) => (col.textContent ?? '').toUpperCase().includes(filter))
    row.style.display = found ? '' : 'none'
  }
}
