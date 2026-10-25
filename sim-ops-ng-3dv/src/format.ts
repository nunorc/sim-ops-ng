// Text for the info panel: pass countdowns and link-state badges

// Countdown to a pass-event epoch relative to the simulated `nowTs`; mirrors GroundStationPanel.vue's diffDatesStr
export function countdown(nowTs: number, target: number | null): string {
  if (target == null || target < nowTs) return '—';

  let delta = target - nowTs;
  const days = Math.floor(delta / 86400);
  delta -= days * 86400;
  const hours = Math.floor(delta / 3600);
  delta -= hours * 3600;
  const minutes = Math.floor(delta / 60);
  delta -= minutes * 60;
  const seconds = Math.floor(delta);

  let res = '';
  if (days > 0) res += `${days}d `;
  if (days > 0 || hours > 0) res += `${hours}h `;
  if (days > 0 || hours > 0 || minutes > 0) res += `${minutes}m `;
  res += `${seconds}s`;
  return res;
}

// Downlink: green only at FRAME_LOCK, its best state.
export const DL_STATE_META: Record<string, { cls: string; label: string; color: string }> = {
  FRAME_LOCK: { cls: 'frame-lock', label: 'FRAME LOCK', color: '#3cd2a5' },
  BIT_LOCK:   { cls: 'bit-lock',   label: 'BIT LOCK',   color: '#ff9f0c' },
  PSK_LOCK:   { cls: 'psk-lock',   label: 'PSK LOCK',   color: '#ff9f0c' },
  PLL_LOCK:   { cls: 'pll-lock',   label: 'PLL LOCK',   color: '#ff9f0c' },
  RF_DETECTED:{ cls: 'rf-detected', label: 'RF DETECTED', color: '#ff9f0c' },
  NO_RF:      { cls: 'no-rf',      label: 'NO RF',      color: '#ff6060' },
};

// Uplink: green at BIT_LOCK, its best state; a separate CSS class since BIT_LOCK means less on the downlink
export const UL_STATE_META: Record<string, { cls: string; label: string; color: string }> = {
  BIT_LOCK: { cls: 'ul-bit-lock', label: 'BIT LOCK', color: '#3cd2a5' },
  NO_RF:    { cls: 'no-rf',       label: 'NO RF',     color: '#ff6060' },
};

export function stateBadge(state: string | undefined, meta: Record<string, { cls: string; label: string; color: string }>): string {
  const s = state ?? 'NO_RF';
  const m = meta[s] ?? { cls: 'no-rf', label: s };
  return `<span class="badge ${m.cls}">${m.label}</span>`;
}
