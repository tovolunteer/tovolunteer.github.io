export function parseFsa(input) {
  const match = /^([A-Z][0-9][A-Z])(?:\s?[0-9][A-Z][0-9])?$/i.exec(input.trim());
  return match ? match[1].toUpperCase() : null;
}

export function lookupFsa(input, centroids) {
  const fsa = parseFsa(input);
  return fsa && Object.hasOwn(centroids, fsa) ? centroids[fsa] : null;
}

export function coordinatesOf(place) {
  if (!place) return null;
  const coordinates = Array.isArray(place) ? place : [place.lat, place.lng];
  const [lat, lng] = coordinates;
  return typeof lat === 'number' && Number.isFinite(lat) && Math.abs(lat) <= 90
    && typeof lng === 'number' && Number.isFinite(lng) && Math.abs(lng) <= 180
    ? [lat, lng] : null;
}

export function haversineKm(from, to) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const latitude = radians(to[0] - from[0]);
  const longitude = radians(to[1] - from[1]);
  const a = Math.sin(latitude / 2) ** 2
    + Math.cos(radians(from[0])) * Math.cos(radians(to[0])) * Math.sin(longitude / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function sortByDistance(items, origin, getCoordinates = (item) => item.coordinates) {
  return [...items].sort((a, b) => {
    const aCoords = coordinatesOf(getCoordinates(a));
    const bCoords = coordinatesOf(getCoordinates(b));
    const aDistance = aCoords ? haversineKm(origin, aCoords) : Infinity;
    const bDistance = bCoords ? haversineKm(origin, bCoords) : Infinity;
    return aDistance - bDistance;
  });
}

export function mapUrl(location, place) {
  if (!location || !location.trim()) return null;
  const coordinates = coordinatesOf(place);
  const query = coordinates ? coordinates.join(',') : encodeURIComponent(location);
  return `https://www.google.com/maps/search/?api=1&query=${query}`;
}
