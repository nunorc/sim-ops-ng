// Command ack "{rel}:REL {acc}:ACC {exe}:EXE", each g (OK), w (warning), r (failed) or u (unknown, no telemetry)
interface AckStage {
  label: string
  cls: string
}

const STAGE_CLASS: Record<string, string> = {
  g: 'text-theme',
  w: 'text-warning',
  u: 'text-warning',
  r: 'text-danger',
}

export function parseAck(status: string | null | undefined): AckStage[] {
  if (!status) return []
  return status.trim().split(/\s+/).map((part) => {
    const [flag, label] = part.includes(':') ? part.split(':', 2) : ['', part]
    return { label: label ?? '', cls: STAGE_CLASS[flag ?? ''] ?? 'text-danger' }
  })
}
