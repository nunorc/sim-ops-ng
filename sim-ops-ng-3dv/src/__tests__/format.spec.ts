import { describe, expect, it } from 'vitest';
import { countdown, stateBadge, DL_STATE_META, UL_STATE_META } from '../format';

describe('countdown', () => {
  it('shows only the units that matter', () => {
    expect(countdown(1000, 1042)).toBe('42s');
    expect(countdown(1000, 1000 + 5 * 60 + 3)).toBe('5m 3s');
    expect(countdown(1000, 1000 + 2 * 3600 + 7)).toBe('2h 0m 7s');
    expect(countdown(0, 86400 + 3600 + 60 + 1)).toBe('1d 1h 1m 1s');
  });

  it('is a dash with no pass or a pass already started', () => {
    expect(countdown(1000, null)).toBe('—');
    expect(countdown(1000, 999)).toBe('—');
    expect(countdown(1000, 1000)).toBe('0s');
  });
});

describe('stateBadge', () => {
  it('labels the link state', () => {
    expect(stateBadge('FRAME_LOCK', DL_STATE_META)).toBe('<span class="badge frame-lock">FRAME LOCK</span>');
    expect(stateBadge('BIT_LOCK', UL_STATE_META)).toBe('<span class="badge ul-bit-lock">BIT LOCK</span>');
  });

  it('reads a missing state as no RF, and shows an unknown one as is', () => {
    expect(stateBadge(undefined, DL_STATE_META)).toBe('<span class="badge no-rf">NO RF</span>');
    expect(stateBadge('PSK_LOCK', UL_STATE_META)).toBe('<span class="badge no-rf">PSK_LOCK</span>');
  });

  it('covers every downlink state the backend sends (TTCState in so/data_model.py)', () => {
    expect(Object.keys(DL_STATE_META).sort()).toEqual(
      ['BIT_LOCK', 'FRAME_LOCK', 'NO_RF', 'PLL_LOCK', 'PSK_LOCK', 'RF_DETECTED']
    );
  });
});
