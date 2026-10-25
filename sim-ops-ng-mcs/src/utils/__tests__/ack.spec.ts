import { describe, expect, it } from 'vitest'
import { parseAck } from '../ack'

describe('parseAck', () => {
  it('maps each stage flag to a colour', () => {
    expect(parseAck('g:REL u:ACC r:EXE')).toEqual([
      { label: 'REL', cls: 'text-theme' },
      { label: 'ACC', cls: 'text-warning' },
      { label: 'EXE', cls: 'text-danger' },
    ])
    expect(parseAck('g:REL w:ACC g:EXE')[1]).toEqual({ label: 'ACC', cls: 'text-warning' })
  })

  it('handles missing or unexpected statuses', () => {
    expect(parseAck(null)).toEqual([])
    expect(parseAck('')).toEqual([])
    expect(parseAck('FAIL')).toEqual([{ label: 'FAIL', cls: 'text-danger' }])
  })
})
