// Spherical-Earth geometry for the scene, kept free of Cesium so it can be unit tested

export function rotateAzimuth(east: number, north: number, angleRad: number): [number, number] {
  const cos = Math.cos(angleRad);
  const sin = Math.sin(angleRad);
  return [east * cos - north * sin, east * sin + north * cos];
}

// Radius (great-circle surface distance, metres) of the visibility circle
// around a ground station at which a spacecraft at the given altitude
// crosses a given minimum elevation angle. Standard spherical-Earth
// look-angle geometry (e.g. Curtis, "Orbital Mechanics for Engineering
// Students"): with Re = mean Earth radius, ρ = Re + h, ε = elevation,
//   λ(ε) = 90° − ε − asin((Re / ρ) · cos ε)
// which reduces to the simple horizon formula cos(λ) = Re/ρ at ε = 0.
// Ignores atmospheric refraction and ground station altitude —
// illustrative, not the backend's actual elevation computation.
export const EARTH_MEAN_RADIUS_M = 6_371_000;
export function horizonRadiusMeters(altitudeKm: number, elevationDeg = 0): number {
  const h = Math.max(altitudeKm, 0) * 1000;
  const rho = EARTH_MEAN_RADIUS_M + h;
  const elevRad = (elevationDeg * Math.PI) / 180;
  const angleAtSatellite = Math.asin((EARTH_MEAN_RADIUS_M / rho) * Math.cos(elevRad));
  const centralAngle = Math.PI / 2 - elevRad - angleAtSatellite;
  return EARTH_MEAN_RADIUS_M * centralAngle;
}
