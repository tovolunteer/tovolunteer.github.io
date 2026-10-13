import test from 'node:test';
import assert from 'node:assert/strict';
import { seasonStatus, torontoMonth } from '../src/lib/season.mjs';

test('year-round programs stay available', () => {
  assert.deepEqual(seasonStatus('year-round', 2), { kind: 'year-round' });
});

test('a listed month is open now', () => {
  assert.deepEqual(seasonStatus([4, 5, 9, 10], 9), { kind: 'open' });
});

test('the next month wraps across the year', () => {
  assert.deepEqual(seasonStatus([11, 12, 1], 2), { kind: 'seasonal', nextMonth: 11 });
  assert.deepEqual(seasonStatus([4, 5, 9, 10], 11), { kind: 'seasonal', nextMonth: 4 });
});

test('unknown or missing months have no status', () => {
  assert.equal(seasonStatus(null, 2), null);
  assert.equal(seasonStatus(undefined, 2), null);
});

test('current month uses Toronto time at the UTC month boundary', () => {
  assert.equal(torontoMonth(new Date('2026-03-01T00:30:00Z')), 2);
  assert.equal(torontoMonth(new Date('2026-03-01T05:30:00Z')), 3);
});
