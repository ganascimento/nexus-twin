export function interpolatePosition(
  path: [number, number][],
  timestamps: number[],
  currentTime: number,
): [number, number] {
  if (path.length === 0) return [0, 0];
  if (currentTime <= timestamps[0]) return path[0];
  if (currentTime >= timestamps[timestamps.length - 1]) return path[path.length - 1];

  let segmentIndex = 0;
  for (let i = 0; i < timestamps.length - 1; i++) {
    if (timestamps[i] <= currentTime && currentTime < timestamps[i + 1]) {
      segmentIndex = i;
      break;
    }
  }

  const t =
    (currentTime - timestamps[segmentIndex]) /
    (timestamps[segmentIndex + 1] - timestamps[segmentIndex]);

  const [lng0, lat0] = path[segmentIndex];
  const [lng1, lat1] = path[segmentIndex + 1];

  return [lng0 + t * (lng1 - lng0), lat0 + t * (lat1 - lat0)];
}

export function calculateBearing(
  from: [number, number],
  to: [number, number],
): number {
  const toRadians = (deg: number) => (deg * Math.PI) / 180;
  const toDegrees = (rad: number) => (rad * 180) / Math.PI;

  const lat1 = toRadians(from[1]);
  const lat2 = toRadians(to[1]);
  const dLng = toRadians(to[0] - from[0]);

  const y = Math.sin(dLng) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);

  return (toDegrees(Math.atan2(y, x)) + 360) % 360;
}
