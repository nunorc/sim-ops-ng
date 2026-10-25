import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { horizonRadiusMeters, rotateAzimuth } from './geometry';
import { countdown, stateBadge, DL_STATE_META, UL_STATE_META } from './format';

// ── Environment ────────────────────────────────────────────────────────────
const CESIUM_TOKEN = import.meta.env.VITE_CESIUM_TOKEN as string ?? '';

// Viewer WebSocket from the page origin: no password, and not SLE-filtered so position updates without FRAME_LOCK
const WS_URL = window.location.origin.replace(/^http/, 'ws') + '/api/ws/viewer';

// Reconnect backoff after a drop (API restarted, network blip, ...)
const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 15000;

if (CESIUM_TOKEN) {
  Cesium.Ion.defaultAccessToken = CESIUM_TOKEN;
}

// ── Types ──────────────────────────────────────────────────────────────────
interface GroundStationConfig {
  name: string;
  latitude: number;
  longitude: number;
  altitude: number; // metres
}

interface GroundStationState {
  elevation: number | null;
  distance: number | null;
  ul_state: string;    // TTCState enum name
  status_dl: string;   // TTCState enum name
  // pass-prediction epoch timestamps (seconds), null when no upcoming pass is known
  next_pass_start: number | null;
  next_pass_end: number | null;
  next_5_start: number | null;
  next_5_end: number | null;
}

interface SpacecraftState {
  aocs_position: [number, number, number]; // [lat_deg, lon_deg, alt_km]
  aocs_rotation: [number, number, number]; // [roll, pitch, yaw] degrees
  aocs_mode: string;
}

interface SimOpsMessage {
  type: string;
  ts: number; // simulated time (epoch seconds), used as the countdown reference
  // Always present on the viewer feed (/api/ws/viewer), regardless of comms link status
  spacecraft: SpacecraftState;
  ground_station: GroundStationState;
  breakpoint?: { name: string; ground_station: GroundStationConfig };
}

// ── DOM references ─────────────────────────────────────────────────────────
const statusDot     = document.getElementById('status-dot')!;
const statusText    = document.getElementById('status-text')!;
const infoPanel     = document.getElementById('info-panel')!;

document.getElementById('app-version')!.textContent = `v${__APP_VERSION__}`;

// Info panel value elements
const elGsUl    = document.getElementById('gs-ul')!;
const elGsDl    = document.getElementById('gs-dl')!;
const elGsAos   = document.getElementById('gs-aos')!;
const elGsAos5  = document.getElementById('gs-aos5')!;
const elGsLos5  = document.getElementById('gs-los5')!;
const elGsLos   = document.getElementById('gs-los')!;

// ── Cesium Viewer ──────────────────────────────────────────────────────────
const viewer = new Cesium.Viewer('cesiumContainer', {
  timeline: false,
  animation: false,
  baseLayerPicker: false,
  fullscreenButton: false,
  homeButton: false,
  navigationHelpButton: false,
  sceneModePicker: false,
  geocoder: false,
  infoBox: false,
  selectionIndicator: false,
  shouldAnimate: false,
  // Use OSM buildings/imagery without requiring a token
  terrain: CESIUM_TOKEN ? Cesium.Terrain.fromWorldTerrain() : undefined,
});

// Use OpenStreetMap imagery if no Cesium token is provided
if (!CESIUM_TOKEN) {
  viewer.imageryLayers.removeAll();
  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      credit: '© OpenStreetMap contributors',
      maximumLevel: 19,
    })
  );
}

viewer.scene.globe.enableLighting = true;
viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#1d2835');

// ── Cesium Entities ────────────────────────────────────────────────────────
// Models are primitive geometry (no GLB assets), rescaled each frame from camera distance to a constant screen size

// Display state eased toward the latest telemetry every frame (lerp/slerp in onTick), so model and camera don't jitter
let scDisplayPos = Cesium.Cartesian3.fromDegrees(0, 0, 400_000);
let scTargetPos = Cesium.Cartesian3.clone(scDisplayPos);
let scDisplayOrientation = Cesium.Quaternion.clone(Cesium.Quaternion.IDENTITY);
let scTargetOrientation = Cesium.Quaternion.clone(Cesium.Quaternion.IDENTITY);
const SMOOTHING = 0.12;

// On-screen target size for the spacecraft composite, recomputed every frame.
let scModelScale = 1;
const SC_REFERENCE_PX = 95;

// Base CubeSat proportions (arbitrary units — scaled by scModelScale, not metres).
const SC_BUS_DIMS = new Cesium.Cartesian3(1.0, 1.0, 2.4); // east(X) x north(Y) x up(Z), body-local
// Deployed panels: thin in body Z, so the cells face the boresight (-Z), which AOCS points at the Sun in SUN mode
const SC_PANEL_DIMS = new Cesium.Cartesian3(3.0, 1.4, 0.12);
const SC_PANEL_OFFSET_X = SC_BUS_DIMS.x / 2 + SC_PANEL_DIMS.x / 2;
const SC_ANT_LENGTH = 1.3;
const SC_ANT_RADIUS = 0.06;
const SC_ANT_OFFSET_Z = SC_BUS_DIMS.z / 2 + SC_ANT_LENGTH / 2;
const SC_REFERENCE_SPAN = 2 * SC_PANEL_OFFSET_X + SC_PANEL_DIMS.x; // panel-tip to panel-tip

// Pointing arrow from the body -Z face to the mode's target (Earth, Sun, GS); along body -Z for modes without one
const SC_POINTING_VEC_START_Z = -(SC_BUS_DIMS.z / 2);
const SC_POINTING_VEC_LENGTH = 6.8;
const SC_POINTING_VEC_END_Z = SC_POINTING_VEC_START_Z - SC_POINTING_VEC_LENGTH;

let scAocsMode = '';

const scratchSunIcrf = new Cesium.Cartesian3();
const scratchIcrfToFixed = new Cesium.Matrix3();
let lastKnownSunPosFixed: Cesium.Cartesian3 | null = null;

function sunPositionFixed(): Cesium.Cartesian3 | null {
  const time = Cesium.JulianDate.now();
  const sunIcrf = Cesium.Simon1994PlanetaryPositions.computeSunPositionInEarthInertialFrame(time, scratchSunIcrf);
  const icrfToFixed = Cesium.Transforms.computeIcrfToFixedMatrix(time, scratchIcrfToFixed);
  // computeIcrfToFixedMatrix is undefined until EOP data loads: keep the last good value rather than hide the arrow
  if (!icrfToFixed) return lastKnownSunPosFixed;
  lastKnownSunPosFixed = Cesium.Matrix3.multiplyByVector(icrfToFixed, sunIcrf, lastKnownSunPosFixed ?? new Cesium.Cartesian3());
  return lastKnownSunPosFixed;
}

// Unit vector from the spacecraft to the current mode's target, or null if the mode has none
function scPointingTargetDirection(): Cesium.Cartesian3 | null {
  let targetPos: Cesium.Cartesian3 | null;
  switch (scAocsMode) {
    case 'NADIR':
      targetPos = Cesium.Cartesian3.ZERO; // Earth's center, in the fixed/ECEF frame
      break;
    case 'SUN':
      targetPos = sunPositionFixed();
      break;
    case 'TARGET':
      targetPos = currentGsPos;
      break;
    default:
      targetPos = null;
  }
  if (!targetPos) return null;
  return Cesium.Cartesian3.normalize(
    Cesium.Cartesian3.subtract(targetPos, scDisplayPos, new Cesium.Cartesian3()), new Cesium.Cartesian3());
}

// World orientation whose local -Z (boresight) points along `direction`, independent of the backend's roll/pitch/yaw
function computeAlignedOrientation(direction: Cesium.Cartesian3): Cesium.Quaternion {
  const zAxis = Cesium.Cartesian3.negate(direction, new Cesium.Cartesian3());
  // reference "up" to fix roll around zAxis; switch axis when direction is nearly parallel to it
  let upRef = Cesium.Cartesian3.UNIT_Z;
  if (Math.abs(Cesium.Cartesian3.dot(zAxis, upRef)) > 0.999) {
    upRef = Cesium.Cartesian3.UNIT_X;
  }
  const xAxis = Cesium.Cartesian3.normalize(Cesium.Cartesian3.cross(upRef, zAxis, new Cesium.Cartesian3()), new Cesium.Cartesian3());
  const yAxis = Cesium.Cartesian3.cross(zAxis, xAxis, new Cesium.Cartesian3());
  const rotationMatrix = new Cesium.Matrix3(
    xAxis.x, yAxis.x, zAxis.x,
    xAxis.y, yAxis.y, zAxis.y,
    xAxis.z, yAxis.z, zAxis.z,
  );
  return Cesium.Quaternion.fromRotationMatrix(rotationMatrix, new Cesium.Quaternion());
}

// Body-local offset (scaled by scModelScale), rotated by the spacecraft orientation and added to its position
function scPartPosition(localOffset: Cesium.Cartesian3): Cesium.Cartesian3 {
  const rotation = Cesium.Matrix3.fromQuaternion(scDisplayOrientation, new Cesium.Matrix3());
  const scaled = Cesium.Cartesian3.multiplyByScalar(localOffset, scModelScale, new Cesium.Cartesian3());
  const worldOffset = Cesium.Matrix3.multiplyByVector(rotation, scaled, new Cesium.Cartesian3());
  return Cesium.Cartesian3.add(scDisplayPos, worldOffset, new Cesium.Cartesian3());
}

const scOrientationProperty = new Cesium.CallbackProperty(() => scDisplayOrientation, false);

// ── Tracking-camera azimuth ─────────────────────────────────────────────
// Default tracking-camera azimuth, as a % of a full turn (negative = left), used by viewFrom and the GS reframe
const VIEW_AZIMUTH_OFFSET_PERCENT = -10;
const VIEW_AZIMUTH_OFFSET_RAD = Cesium.Math.toRadians((VIEW_AZIMUTH_OFFSET_PERCENT / 100) * 360);

const [scViewFromEast, scViewFromNorth] = rotateAzimuth(0, -1_150_000, VIEW_AZIMUTH_OFFSET_RAD);

const scEntity = viewer.entities.add({
  name: 'Spacecraft',
  position: new Cesium.CallbackPositionProperty(() => scDisplayPos, false),
  orientation: scOrientationProperty,
  label: {
    text: 'SC',
    font: '14px monospace',
    fillColor: Cesium.Color.WHITE,
    outlineColor: Cesium.Color.BLACK,
    outlineWidth: 2,
    style: Cesium.LabelStyle.FILL_AND_OUTLINE,
    verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
    pixelOffset: new Cesium.Cartesian2(0, -40),
    scaleByDistance: new Cesium.NearFarScalar(1e6, 1.0, 1e8, 0.4),
  },
  // default tracked-camera offset (ENU metres): well back, above, tilted down; re-aimed by reframeTowardGroundStation()
  viewFrom: new Cesium.Cartesian3(scViewFromEast, scViewFromNorth, 780_000),
});

// Smoothed camera offset (ENU metres), eased every frame toward the reframe target so the camera glides
let reframeDisplayOffset = new Cesium.Cartesian3(scViewFromEast, scViewFromNorth, 780_000);
let reframeTargetOffset = Cesium.Cartesian3.clone(reframeDisplayOffset);

const scBusEntity = viewer.entities.add({
  name: 'Spacecraft bus',
  position: new Cesium.CallbackPositionProperty(() => scPartPosition(Cesium.Cartesian3.ZERO), false),
  orientation: scOrientationProperty,
  box: {
    dimensions: new Cesium.CallbackProperty(
      () => Cesium.Cartesian3.multiplyByScalar(SC_BUS_DIMS, scModelScale, new Cesium.Cartesian3()), false),
    material: Cesium.Color.fromCssColorString('#cdd5db'),
    outline: true,
    outlineColor: Cesium.Color.BLACK,
  },
});

// Two deployed solar panels, one on either side of the bus.
const scPanelEntities = [-1, 1].map((side) => viewer.entities.add({
  name: side < 0 ? 'Spacecraft panel (-X)' : 'Spacecraft panel (+X)',
  position: new Cesium.CallbackPositionProperty(
    () => scPartPosition(new Cesium.Cartesian3(side * SC_PANEL_OFFSET_X, 0, 0)), false),
  orientation: scOrientationProperty,
  box: {
    dimensions: new Cesium.CallbackProperty(
      () => Cesium.Cartesian3.multiplyByScalar(SC_PANEL_DIMS, scModelScale, new Cesium.Cartesian3()), false),
    material: Cesium.Color.fromCssColorString('#1b2a4a'),
    outline: true,
    outlineColor: Cesium.Color.fromCssColorString('#3cd2a5'),
  },
}));

const scAntennaEntity = viewer.entities.add({
  name: 'Spacecraft antenna',
  position: new Cesium.CallbackPositionProperty(
    () => scPartPosition(new Cesium.Cartesian3(0, 0, SC_ANT_OFFSET_Z)), false),
  orientation: scOrientationProperty,
  cylinder: {
    length: new Cesium.CallbackProperty(() => SC_ANT_LENGTH * scModelScale, false),
    topRadius: new Cesium.CallbackProperty(() => SC_ANT_RADIUS * scModelScale, false),
    bottomRadius: new Cesium.CallbackProperty(() => SC_ANT_RADIUS * scModelScale, false),
    material: Cesium.Color.fromCssColorString('#9aa5b1'),
  },
});

// Boresight (body -Z, blue) plus +X (red) and +Y (green): the standard RGB axis triad
const scPointingVectorEntity = viewer.entities.add({
  name: 'Spacecraft pointing direction (body -Z axis)',
  polyline: {
    positions: new Cesium.CallbackProperty(() => {
      const start = scPartPosition(new Cesium.Cartesian3(0, 0, SC_POINTING_VEC_START_Z));
      const dir = scPointingTargetDirection();
      if (!dir) {
        // No defined target for this mode — show the body -Z axis instead.
        return [start, scPartPosition(new Cesium.Cartesian3(0, 0, SC_POINTING_VEC_END_Z))];
      }
      const length = SC_POINTING_VEC_LENGTH * scModelScale;
      const end = Cesium.Cartesian3.add(
        scDisplayPos, Cesium.Cartesian3.multiplyByScalar(dir, length, new Cesium.Cartesian3()), new Cesium.Cartesian3());
      return [start, end];
    }, false),
    width: 10,
    material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.fromCssColorString('#4da6ff')),
    // collinear with the nadir line in NADIR mode: depthFailMaterial keeps it drawn on top instead of z-fighting
    depthFailMaterial: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.fromCssColorString('#4da6ff')),
    arcType: Cesium.ArcType.NONE,
  },
});

const scAxisXVectorEntity = viewer.entities.add({
  name: 'Spacecraft body +X axis',
  polyline: {
    positions: new Cesium.CallbackProperty(() => [
      scPartPosition(Cesium.Cartesian3.ZERO),
      scPartPosition(new Cesium.Cartesian3(SC_POINTING_VEC_LENGTH, 0, 0)),
    ], false),
    width: 10,
    material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.fromCssColorString('#ff4d4d')),
    arcType: Cesium.ArcType.NONE,
  },
});

const scAxisYVectorEntity = viewer.entities.add({
  name: 'Spacecraft body +Y axis',
  polyline: {
    positions: new Cesium.CallbackProperty(() => [
      scPartPosition(Cesium.Cartesian3.ZERO),
      scPartPosition(new Cesium.Cartesian3(0, SC_POINTING_VEC_LENGTH, 0)),
    ], false),
    width: 10,
    material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.fromCssColorString('#3cd2a5')),
    arcType: Cesium.ArcType.NONE,
  },
});

// Camera follows the spacecraft's position (not attitude); the user can still zoom/rotate around it
viewer.trackedEntity = scEntity;

const scratchPixelDims = new Cesium.Cartesian2();
const scratchReframeTransform = new Cesium.Matrix4();
let lastLinkTickMs = Date.now();

viewer.clock.onTick.addEventListener(() => {
  scDisplayPos = Cesium.Cartesian3.lerp(scDisplayPos, scTargetPos, SMOOTHING, scDisplayPos);

  // modes with a target drive the body orientation from geometry, matching the arrow; others use scTargetOrientation
  const pointingDir = scPointingTargetDirection();
  if (pointingDir) {
    scTargetOrientation = computeAlignedOrientation(pointingDir);
  }
  scDisplayOrientation = Cesium.Quaternion.slerp(scDisplayOrientation, scTargetOrientation, SMOOTHING, scDisplayOrientation);

  // ease the camera toward the reframe target via lookAtTransform (trackedEntity would snap), unless the user interacts
  if (Date.now() - lastInteractionTs >= IDLE_BEFORE_REFRAME_MS) {
    reframeDisplayOffset = Cesium.Cartesian3.lerp(reframeDisplayOffset, reframeTargetOffset, SMOOTHING, reframeDisplayOffset);
    const scEnuToFixed = Cesium.Transforms.eastNorthUpToFixedFrame(scDisplayPos, undefined, scratchReframeTransform);
    viewer.camera.lookAtTransform(scEnuToFixed, reframeDisplayOffset);
  }

  const scDistance = Cesium.Cartesian3.distance(viewer.camera.positionWC, scDisplayPos);
  viewer.camera.frustum.getPixelDimensions(
    viewer.scene.drawingBufferWidth, viewer.scene.drawingBufferHeight, scDistance, 1.0, scratchPixelDims);
  scModelScale = (scratchPixelDims.y * SC_REFERENCE_PX) / SC_REFERENCE_SPAN;

  if (currentGsPos) {
    const gsDistance = Cesium.Cartesian3.distance(viewer.camera.positionWC, currentGsPos);
    viewer.camera.frustum.getPixelDimensions(
      viewer.scene.drawingBufferWidth, viewer.scene.drawingBufferHeight, gsDistance, 1.0, scratchPixelDims);
    gsModelScale = (scratchPixelDims.y * GS_REFERENCE_PX) / GS_REFERENCE_SPAN;
  }

  const nowMs = Date.now();
  const dt = (nowMs - lastLinkTickMs) / 1000;
  lastLinkTickMs = nowMs;
  if (linkVisible && currentGsPos) {
    linkPhase += dt * LINK_WAVE_SPEED;
    linkPositions = computeWavyLinkPositions(currentGsPos, scDisplayPos, linkPhase, 1, 1, LINK_WAVE_CYCLES / 2);
  } else {
    linkPositions = [];
  }

  if (uplinkVisible && currentGsPos) {
    // direction -1 reverses chirality and crest travel, so uplink crests run from ground station to spacecraft
    uplinkPhase += dt * UPLINK_WAVE_SPEED;
    uplinkPositions = computeWavyLinkPositions(currentGsPos, scDisplayPos, uplinkPhase, -1, UPLINK_WAVE_AMPLITUDE_SCALE);
  } else {
    uplinkPositions = [];
  }
});

// Ground station entities (added once config arrives): a dish on a pedestal, rescaled like the spacecraft
let gsEntities: Cesium.Entity[] = [];
let currentGsPos: Cesium.Cartesian3 | null = null;
let gsEnuToFixed: Cesium.Matrix4 | null = null;
let gsModelScale = 1;
const GS_REFERENCE_PX = 14;
const GS_PEDESTAL_HEIGHT = 5;
const GS_PEDESTAL_TOP_RADIUS = 0.35;
const GS_PEDESTAL_BOTTOM_RADIUS = 0.6;
const GS_DISH_RADIUS = 3.0;
const GS_DISH_THICKNESS = 0.3;
const GS_DISH_TILT_DEG = -55; // tilt off zenith, purely for a recognizable "dish" look
const GS_REFERENCE_SPAN = GS_DISH_RADIUS * 2;

// Local ENU offset (scaled by gsModelScale), rotated into the fixed frame and added to the GS position
function gsPartPosition(localOffset: Cesium.Cartesian3): Cesium.Cartesian3 {
  if (!currentGsPos || !gsEnuToFixed) return Cesium.Cartesian3.ZERO;
  const scaled = Cesium.Cartesian3.multiplyByScalar(localOffset, gsModelScale, new Cesium.Cartesian3());
  const rotated = Cesium.Matrix4.multiplyByPointAsVector(gsEnuToFixed, scaled, new Cesium.Cartesian3());
  return Cesium.Cartesian3.add(currentGsPos, rotated, new Cesium.Cartesian3());
}

// GS-to-spacecraft link line: an animated corkscrew, so it looks wavy from any angle (a sine goes flat edge-on)
const linkEntity = viewer.entities.add({
  name: 'GS link',
  polyline: {
    positions: new Cesium.CallbackProperty(() => linkPositions, false),
    width: 1.8,
    material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(() => linkColor, false)),
    arcType: Cesium.ArcType.NONE,
  },
});

let linkPositions: Cesium.Cartesian3[] = [];
let linkVisible = false;
let linkPhase = 0;
let linkColor = Cesium.Color.fromCssColorString('#ff6060');

// Uplink: an opposite-handed corkscrew, shown only at BIT_LOCK (its best state, the green badge)
const uplinkEntity = viewer.entities.add({
  name: 'GS uplink',
  polyline: {
    positions: new Cesium.CallbackProperty(() => uplinkPositions, false),
    width: 1.8,
    material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(() => uplinkColor, false)),
    arcType: Cesium.ArcType.NONE,
  },
});

let uplinkPositions: Cesium.Cartesian3[] = [];
let uplinkVisible = false;
let uplinkPhase = 0;
const uplinkColor = Cesium.Color.fromCssColorString('#ff6060');

const LINK_WAVE_SEGMENTS = 192;
const LINK_WAVE_CYCLES = 26;
const LINK_WAVE_SPEED = 4; // radians/sec phase advance, i.e. "signal" travel speed
const UPLINK_WAVE_SPEED = 5; // slightly faster than the downlink, for visual distinction
const UPLINK_WAVE_AMPLITUDE_SCALE = 0.65; // a bit smaller/tighter than the downlink corkscrew
const LINK_WAVE_AMPLITUDE_FRACTION = 0.014; // of link length
const LINK_WAVE_AMPLITUDE_MIN = 2000; // metres
const LINK_WAVE_AMPLITUDE_MAX = 18000; // metres

const scratchLinkDir = new Cesium.Cartesian3();
const scratchLinkUp = new Cesium.Cartesian3();
const scratchLinkU = new Cesium.Cartesian3();
const scratchLinkV = new Cesium.Cartesian3();
const scratchLinkMid = new Cesium.Cartesian3();

// Animated corkscrew path from p0 to p1: a sinusoidal offset in two axes perpendicular to the link
function computeWavyLinkPositions(
  p0: Cesium.Cartesian3, p1: Cesium.Cartesian3, phase: number, direction: 1 | -1 = 1, amplitudeScale = 1,
  cycles = LINK_WAVE_CYCLES,
): Cesium.Cartesian3[] {
  const dir = Cesium.Cartesian3.subtract(p1, p0, scratchLinkDir);
  const length = Cesium.Cartesian3.magnitude(dir);
  if (length < 1) return [p0, p1];
  Cesium.Cartesian3.normalize(dir, dir);

  // radial ("up") direction at the link midpoint, to derive two vectors perpendicular to the link
  const mid = Cesium.Cartesian3.midpoint(p0, p1, scratchLinkMid);
  const up = Cesium.Cartesian3.normalize(mid, scratchLinkUp);

  const u = Cesium.Cartesian3.cross(dir, up, scratchLinkU);
  if (Cesium.Cartesian3.magnitude(u) < 1e-6) {
    // dir is (near-)parallel to radial: use an arbitrary reference axis to avoid a degenerate cross product
    Cesium.Cartesian3.cross(dir, Cesium.Cartesian3.UNIT_X, u);
  }
  Cesium.Cartesian3.normalize(u, u);
  const v = Cesium.Cartesian3.normalize(Cesium.Cartesian3.cross(dir, u, scratchLinkV), scratchLinkV);

  const amplitude = amplitudeScale * Cesium.Math.clamp(
    length * LINK_WAVE_AMPLITUDE_FRACTION, LINK_WAVE_AMPLITUDE_MIN, LINK_WAVE_AMPLITUDE_MAX);

  const positions: Cesium.Cartesian3[] = [];
  for (let i = 0; i <= LINK_WAVE_SEGMENTS; i++) {
    const t = i / LINK_WAVE_SEGMENTS;
    const angle = direction * cycles * 2 * Math.PI * t + phase;
    const point = Cesium.Cartesian3.fromElements(
      p0.x + dir.x * length * t + u.x * amplitude * Math.cos(angle) + v.x * amplitude * Math.sin(angle),
      p0.y + dir.y * length * t + u.y * amplitude * Math.cos(angle) + v.y * amplitude * Math.sin(angle),
      p0.z + dir.z * length * t + u.z * amplitude * Math.cos(angle) + v.z * amplitude * Math.sin(angle),
    );
    positions.push(point);
  }
  return positions;
}

// Nadir line: from the spacecraft straight down to its ground-track point
const scratchNadirCarto = new Cesium.Cartographic();
let scNadirGroundPoint = new Cesium.Cartesian3();

function computeScNadirGroundPoint(): Cesium.Cartesian3 {
  const carto = Cesium.Ellipsoid.WGS84.cartesianToCartographic(scDisplayPos, scratchNadirCarto);
  scNadirGroundPoint = Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, 0, Cesium.Ellipsoid.WGS84, scNadirGroundPoint);
  return scNadirGroundPoint;
}

// Disabled: redundant with the ground track + nadir marker, and it collided with the boresight in NADIR mode
const SHOW_NADIR_LINE = false;

const scNadirLineEntity = viewer.entities.add({
  name: 'Spacecraft nadir line',
  show: SHOW_NADIR_LINE,
  polyline: {
    positions: new Cesium.CallbackProperty(() => [scDisplayPos, computeScNadirGroundPoint()], false),
    width: 1.5,
    material: Cesium.Color.fromCssColorString('#d3d3d3'),
    arcType: Cesium.ArcType.NONE,
  },
});

// Sub-satellite point marker: a small white dot where the nadir line meets the ground
const scNadirPointEntity = viewer.entities.add({
  name: 'Spacecraft nadir ground point',
  position: new Cesium.CallbackPositionProperty(() => computeScNadirGroundPoint(), false),
  point: {
    pixelSize: 5,
    color: Cesium.Color.WHITE,
    disableDepthTestDistance: Number.POSITIVE_INFINITY,
  },
});

// Ground track: a grey dashed trail of past sub-satellite points, capped at GROUND_TRACK_MAX_POINTS
const GROUND_TRACK_MAX_POINTS = 600;
let groundTrackPositions: Cesium.Cartesian3[] = [];

const scGroundTrackEntity = viewer.entities.add({
  name: 'Spacecraft ground track',
  polyline: {
    positions: new Cesium.CallbackProperty(() => groundTrackPositions, false),
    width: 2,
    material: new Cesium.PolylineDashMaterialProperty({
      color: Cesium.Color.fromCssColorString('#d3d3d3'),
      dashLength: 12,
    }),
    arcType: Cesium.ArcType.GEODESIC,
  },
});

// ── Mutable state ──────────────────────────────────────────────────────────
let currentGsConfig: GroundStationConfig | null = null;
let currentBreakpointName: string | null = null;
let lastScPos: Cesium.Cartesian3 | null = null;
let scAltKm = 0;
let socket: WebSocket | null = null;
let reconnectDelayMs = RECONNECT_MIN_MS;

// ── Camera: keep it generally aimed toward the ground station ─────────────
// Periodically re-aim the camera target offset toward the ground station, unless the user recently zoomed/dragged
let lastInteractionTs = 0;
const IDLE_BEFORE_REFRAME_MS = 4000;
const REFRAME_INTERVAL_MS = 2000;
let lastReframeTs = 0;
const REFRAME_BACK_M = 1_150_000; // metres behind the spacecraft, away from the GS bearing
const REFRAME_UP_M = 780_000;     // metres above the spacecraft — gentle tilt, keeps the horizon in view

for (const evt of ['wheel', 'mousedown', 'touchstart', 'pointerdown']) {
  viewer.canvas.addEventListener(evt, () => { lastInteractionTs = Date.now(); }, { passive: true });
}

function reframeTowardGroundStation(scPos: Cesium.Cartesian3, gsPos: Cesium.Cartesian3): void {
  const now = Date.now();
  if (now - lastInteractionTs < IDLE_BEFORE_REFRAME_MS) return;
  if (now - lastReframeTs < REFRAME_INTERVAL_MS) return;
  lastReframeTs = now;

  const enuToFixed = Cesium.Transforms.eastNorthUpToFixedFrame(scPos);
  const fixedToEnu = Cesium.Matrix4.inverseTransformation(enuToFixed, new Cesium.Matrix4());
  const gsLocal = Cesium.Matrix4.multiplyByPoint(fixedToEnu, gsPos, new Cesium.Cartesian3());

  const horizLen = Math.hypot(gsLocal.x, gsLocal.y) || 1;
  const dirEast = gsLocal.x / horizLen;
  const dirNorth = gsLocal.y / horizLen;

  // camera behind the spacecraft opposite the GS (rotated by VIEW_AZIMUTH_OFFSET_PERCENT), so it looks toward the GS
  const [reframeEast, reframeNorth] = rotateAzimuth(
    -dirEast * REFRAME_BACK_M, -dirNorth * REFRAME_BACK_M, VIEW_AZIMUTH_OFFSET_RAD);
  // only update the target; onTick eases the camera toward it every frame
  reframeTargetOffset = new Cesium.Cartesian3(reframeEast, reframeNorth, REFRAME_UP_M);
}

function ensureGroundStation(cfg: GroundStationConfig): void {
  // breakpoints can use different stations, or the same name at another location
  if (gsEntities.length > 0 && currentGsConfig
      && currentGsConfig.name === cfg.name
      && currentGsConfig.latitude === cfg.latitude
      && currentGsConfig.longitude === cfg.longitude
      && currentGsConfig.altitude === cfg.altitude) return;

  for (const e of gsEntities) viewer.entities.remove(e);
  gsEntities = [];

  currentGsPos = Cesium.Cartesian3.fromDegrees(cfg.longitude, cfg.latitude, cfg.altitude);
  gsEnuToFixed = Cesium.Transforms.eastNorthUpToFixedFrame(currentGsPos);
  const gsOrientation = new Cesium.ConstantProperty(
    Cesium.Transforms.headingPitchRollQuaternion(currentGsPos, new Cesium.HeadingPitchRoll(0, 0, 0)));
  const gsDishOrientation = new Cesium.ConstantProperty(
    Cesium.Transforms.headingPitchRollQuaternion(
      currentGsPos, new Cesium.HeadingPitchRoll(0, Cesium.Math.toRadians(GS_DISH_TILT_DEG), 0)));

  const pedestalEntity = viewer.entities.add({
    name: `${cfg.name} pedestal`,
    position: new Cesium.CallbackPositionProperty(
      () => gsPartPosition(new Cesium.Cartesian3(0, 0, GS_PEDESTAL_HEIGHT / 2)), false),
    orientation: gsOrientation,
    cylinder: {
      length: new Cesium.CallbackProperty(() => GS_PEDESTAL_HEIGHT * gsModelScale, false),
      topRadius: new Cesium.CallbackProperty(() => GS_PEDESTAL_TOP_RADIUS * gsModelScale, false),
      bottomRadius: new Cesium.CallbackProperty(() => GS_PEDESTAL_BOTTOM_RADIUS * gsModelScale, false),
      material: Cesium.Color.fromCssColorString('#4e5562'),
    },
    label: {
      text: cfg.name,
      font: '14px monospace',
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -34),
      scaleByDistance: new Cesium.NearFarScalar(1e5, 1.0, 5e7, 0.5),
    },
  });

  const dishEntity = viewer.entities.add({
    name: `${cfg.name} dish`,
    position: new Cesium.CallbackPositionProperty(
      () => gsPartPosition(new Cesium.Cartesian3(0, 0, GS_PEDESTAL_HEIGHT)), false),
    orientation: gsDishOrientation,
    cylinder: {
      length: new Cesium.CallbackProperty(() => GS_DISH_THICKNESS * gsModelScale, false),
      topRadius: new Cesium.CallbackProperty(() => GS_DISH_RADIUS * 0.12 * gsModelScale, false),
      bottomRadius: new Cesium.CallbackProperty(() => GS_DISH_RADIUS * gsModelScale, false),
      material: Cesium.Color.fromCssColorString('#e8ecf1').withAlpha(0.95),
      outline: true,
      outlineColor: Cesium.Color.BLACK,
    },
  });

  // horizon masks: 0° (visibility) and 5° elevation circles, radii re-read from scAltKm every frame
  const horizonEntity = viewer.entities.add({
    name: `${cfg.name} horizon (0°)`,
    position: currentGsPos,
    ellipse: {
      semiMajorAxis: new Cesium.CallbackProperty(() => horizonRadiusMeters(scAltKm, 0), false),
      semiMinorAxis: new Cesium.CallbackProperty(() => horizonRadiusMeters(scAltKm, 0), false),
      height: cfg.altitude,
      fill: true,
      material: Cesium.Color.fromCssColorString('#90ee90').withAlpha(0.06),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#90ee90'),
      outlineWidth: 2,
    },
  });

  const horizon5Entity = viewer.entities.add({
    name: `${cfg.name} horizon (5°)`,
    position: currentGsPos,
    ellipse: {
      semiMajorAxis: new Cesium.CallbackProperty(() => horizonRadiusMeters(scAltKm, 5), false),
      semiMinorAxis: new Cesium.CallbackProperty(() => horizonRadiusMeters(scAltKm, 5), false),
      height: cfg.altitude,
      fill: true,
      material: Cesium.Color.fromCssColorString('#ff6060').withAlpha(0.06),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#ff6060'),
      outlineWidth: 2,
    },
  });

  gsEntities = [pedestalEntity, dishEntity, horizonEntity, horizon5Entity];
  currentGsConfig = cfg;
}

function onStateMessage(msg: SimOpsMessage): void {
  const sc = msg.spacecraft;
  const gs = msg.ground_station;
  const bpGs = msg.breakpoint?.ground_station;
  const bpName = msg.breakpoint?.name;

  // ── Ground station ──────────────────────────────────────────────────────
  if (bpGs) {
    ensureGroundStation(bpGs);
  }

  // a new breakpoint may reuse the ground station, so clear the trail when the breakpoint name changes
  if (bpName !== undefined && bpName !== currentBreakpointName) {
    currentBreakpointName = bpName;
    groundTrackPositions = [];
  }

  // ── Spacecraft position/orientation ─────────────────────────────────────
  // always updated: position/attitude is ground truth, not gated by FRAME_LOCK
  const [lat, lon, altKm] = sc.aocs_position;
  scAltKm = altKm;

  // Ignore un-initialised zeros
  if (!(lat === 0 && lon === 0 && altKm === 0)) {
    const altM = altKm * 1000;
    const scPos = Cesium.Cartesian3.fromDegrees(lon, lat, altM);
    scTargetPos = scPos;
    lastScPos = scPos;

    groundTrackPositions.push(Cesium.Cartesian3.fromDegrees(lon, lat, 0));
    if (groundTrackPositions.length > GROUND_TRACK_MAX_POINTS) {
      groundTrackPositions.shift();
    }

    // ── Orientation (roll, pitch, yaw → heading-pitch-roll) ─────────────
    const [roll, pitch, yaw] = sc.aocs_rotation;
    const hpr = new Cesium.HeadingPitchRoll(
      Cesium.Math.toRadians(yaw),
      Cesium.Math.toRadians(pitch),
      Cesium.Math.toRadians(roll),
    );
    scTargetOrientation = Cesium.Transforms.headingPitchRollQuaternion(scPos, hpr);

    if (currentGsConfig) {
      const gsPos = Cesium.Cartesian3.fromDegrees(
        currentGsConfig.longitude,
        currentGsConfig.latitude,
        currentGsConfig.altitude,
      );
      reframeTowardGroundStation(scPos, gsPos);
    }
  }

  // the AOCS mode is only trusted at FRAME_LOCK, otherwise assume NADIR; drives the model orientation
  const trustedAocsMode = gs.status_dl === 'FRAME_LOCK' ? (sc.aocs_mode ?? '') : 'NADIR';
  scAocsMode = trustedAocsMode;

  // ── GS link line ────────────────────────────────────────────────────────
  // geometry is regenerated every frame in onTick so the wave animates; this toggles visibility and color
  linkVisible = !!(currentGsConfig && lastScPos && gs.elevation != null && gs.elevation > 0);
  const linkStateMeta = DL_STATE_META[gs.status_dl] ?? DL_STATE_META.NO_RF;
  linkColor = Cesium.Color.fromCssColorString(linkStateMeta.color);

  // ── GS uplink line ──────────────────────────────────────────────────────
  // fixed red color, distinct from the downlink beam regardless of state
  uplinkVisible = !!(
    currentGsConfig && lastScPos && gs.elevation != null && gs.elevation > 0 && gs.ul_state === 'BIT_LOCK'
  );

  // ── Info panel (ground station link status) ───────────────────────────
  elGsUl.innerHTML = stateBadge(gs.ul_state, UL_STATE_META);
  elGsDl.innerHTML = stateBadge(gs.status_dl, DL_STATE_META);

  // ── Pass predictions ────────────────────────────────────────────────
  elGsAos.textContent  = countdown(msg.ts, gs.next_pass_start);
  elGsAos5.textContent = countdown(msg.ts, gs.next_5_start);
  elGsLos5.textContent = countdown(msg.ts, gs.next_5_end);
  elGsLos.textContent  = countdown(msg.ts, gs.next_pass_end);

  infoPanel.classList.add('visible');
}

// ── WebSocket ──────────────────────────────────────────────────────────────
function setStatus(state: 'connected' | 'disconnected', text: string): void {
  statusDot.className = state;
  statusDot.title = text;
  statusText.textContent = state === 'connected' ? '' : text;
}

function connect(): void {
  socket = new WebSocket(WS_URL);

  socket.addEventListener('open', () => {
    reconnectDelayMs = RECONNECT_MIN_MS;
    setStatus('connected', 'Connected');
    // the API sends the latest state (current breakpoint included) straight away
  });

  socket.addEventListener('message', (ev: MessageEvent) => {
    let msg: SimOpsMessage;
    try {
      msg = JSON.parse(ev.data as string) as SimOpsMessage;
    } catch {
      return;
    }
    if (msg.type === 'state' && msg.spacecraft) {
      onStateMessage(msg);
    }
  });

  // 'close' also follows a failed connection attempt: covers both a drop and an unreachable server
  socket.addEventListener('close', () => {
    socket = null;
    const seconds = Math.round(reconnectDelayMs / 1000);
    setStatus('disconnected', `Disconnected — retrying in ${seconds}s`);
    setTimeout(connect, reconnectDelayMs);
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, RECONNECT_MAX_MS);
  });
}

connect();

// Suppress lint warnings for entities only used via callbacks
void linkEntity;
void uplinkEntity;
void scNadirLineEntity;
void scNadirPointEntity;
void scGroundTrackEntity;
void scBusEntity;
void scPanelEntities;
void scAntennaEntity;
void scPointingVectorEntity;
void scAxisXVectorEntity;
void scAxisYVectorEntity;
