import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { loadData } from '../src/lib/data.mjs';

const dataRoot = fileURLToPath(new URL('./fixtures/data/', import.meta.url));

test('loads multiple sources, removes expired events, and parses both YAML lists', async () => {
  const data = await loadData({ dataRoot, now: new Date('2026-10-13T12:00:00Z') });

  assert.deepEqual(data.sources.map(({ source, status }) => [source, status]), [
    ['first', 'ok'], ['second', 'error'],
  ]);
  assert.deepEqual(data.events.map(({ id, source }) => [id, source]), [
    ['second:ongoing', 'second'], ['first:future', 'first'],
  ]);
  assert.equal(data.events[1].fetched_at, '2026-10-13T10:00:00Z');
  assert.equal(data.programs[0].title, 'Fixture program');
  assert.equal(data.programs[0].min_age, null);
  assert.equal(data.foodbanks[0].name, 'Fixture bank');
  assert.equal(data.foodbanks[0].last_verified, '2026-10-12');
  assert.deepEqual(data.places['first:future'], { lat: 43.66, lng: -79.39, query: 'Toronto' });
  assert.equal(data.hasAutoEvents, true);
});

test('missing places file is empty and expired automatic section is hidden', async () => {
  const data = await loadData({
    dataRoot,
    now: new Date('2027-01-01T00:00:00Z'),
    placesPath: fileURLToPath(new URL('./fixtures/data/geo/missing.json', import.meta.url)),
  });
  assert.deepEqual(data.places, {});
  assert.deepEqual(data.events, []);
  assert.equal(data.hasAutoEvents, false);
});
