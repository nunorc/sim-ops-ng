import { describe, expect, it } from 'vitest';
import { EARTH_MEAN_RADIUS_M, horizonRadiusMeters, rotateAzimuth } from '../geometry';

describe('horizonRadiusMeters', () => {
  it('matches the horizon formula cos(λ) = Re / (Re + h) at 0° elevation', () => {
    const h = 500_000;
    const expected = EARTH_MEAN_RADIUS_M * Math.acos(EARTH_MEAN_RADIUS_M / (EARTH_MEAN_RADIUS_M + h));
    expect(horizonRadiusMeters(500)).toBeCloseTo(expected, 3);
    // ~2445 km of ground range for a 500 km LEO
    expect(horizonRadiusMeters(500) / 1000).toBeCloseTo(2445, 0);
  });

  it('shrinks with the minimum elevation, and grows with altitude', () => {
    expect(horizonRadiusMeters(500, 5)).toBeLessThan(horizonRadiusMeters(500, 0));
    expect(horizonRadiusMeters(800)).toBeGreaterThan(horizonRadiusMeters(500));
  });

  it('is zero on the ground, even for a negative altitude', () => {
    expect(horizonRadiusMeters(0)).toBe(0);
    expect(horizonRadiusMeters(-10)).toBe(0);
  });
});

describe('rotateAzimuth', () => {
  it('rotates an east/north offset counter-clockwise, preserving its length', () => {
    const [east, north] = rotateAzimuth(1, 0, Math.PI / 2);
    expect(east).toBeCloseTo(0);
    expect(north).toBeCloseTo(1);

    const [e2, n2] = rotateAzimuth(0, -1_150_000, -Math.PI / 5);
    expect(Math.hypot(e2, n2)).toBeCloseTo(1_150_000, 3);
  });
});
