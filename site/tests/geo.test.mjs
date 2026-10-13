import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { coordinatesOf, haversineKm, lookupFsa, mapUrl, parseFsa, sortByDistance } from '../src/lib/geo.mjs';

const centroids = JSON.parse(await readFile(new URL('../../data/geo/fsa.json', import.meta.url), 'utf8'));

test('parses full and short postal codes and rejects unknown codes', () => {
  for (const value of ['M5V 2T6', 'm5v2t6', 'M5V']) {
    assert.equal(parseFsa(value), 'M5V');
    assert.deepEqual(lookupFsa(value, centroids), [43.6404, -79.3995]);
  }
  assert.equal(parseFsa('M5V!'), null);
  assert.equal(lookupFsa('ZZZ', centroids), null);
});

test('haversine uses actual M5V and M4C centroid coordinates', () => {
  assert.ok(Math.abs(haversineKm(centroids.M5V, centroids.M4C) - 9.05666) < 0.001);
  assert.equal(haversineKm(centroids.M5V, centroids.M5V), 0);
});

test('distance sorting puts missing coordinates last without mutating source order', () => {
  const items = [
    { id: 'missing', coordinates: null },
    { id: 'far', coordinates: centroids.M4C },
    { id: 'near', coordinates: centroids.M5V },
  ];
  assert.deepEqual(sortByDistance(items, centroids.M5V).map(({ id }) => id), ['near', 'far', 'missing']);
  assert.equal(items[0].id, 'missing');
  assert.equal(coordinatesOf({ lat: null, lng: -79.4 }), null);
});

test('map links use coordinates when available and encoded location otherwise', () => {
  assert.equal(mapUrl('Main St, Toronto', { lat: 43.66, lng: -79.39 }),
    'https://www.google.com/maps/search/?api=1&query=43.66,-79.39');
  assert.equal(mapUrl('Main St, Toronto', null),
    'https://www.google.com/maps/search/?api=1&query=Main%20St%2C%20Toronto');
  assert.equal(mapUrl('', { lat: 43.66, lng: -79.39 }), null);
});
