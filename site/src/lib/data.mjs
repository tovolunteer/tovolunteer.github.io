import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import YAML from 'yaml';

const defaultDataRoot = fileURLToPath(new URL('../../../data/', import.meta.url));

function upcoming(event, now) {
  const endpoint = event.end || event.start;
  const timestamp = Date.parse(endpoint);
  return Number.isFinite(timestamp) && timestamp >= now.getTime();
}

export async function loadData({ dataRoot = defaultDataRoot, now = new Date(), placesPath = path.join(dataRoot, 'geo', 'places.json') } = {}) {
  const autoDir = path.join(dataRoot, 'auto');
  const files = (await readdir(autoDir)).filter((name) => name.endsWith('.json')).sort();
  const sources = await Promise.all(files.map(async (name) => {
    const source = JSON.parse(await readFile(path.join(autoDir, name), 'utf8'));
    return {
      source: source.source,
      status: source.status,
      fetched_at: source.fetched_at,
      events: Array.isArray(source.events) ? source.events : [],
    };
  }));
  const events = sources.flatMap((source) => source.events.map((event) => ({
    ...event,
    source: event.source || source.source,
    fetched_at: source.fetched_at,
  }))).filter((event) => upcoming(event, now)).sort((a, b) =>
    Date.parse(a.start) - Date.parse(b.start) || a.id.localeCompare(b.id));
  const manual = path.join(dataRoot, 'manual');
  const directories = await readFile(path.join(manual, 'directories.yaml'), 'utf8').then((text) => YAML.parse(text) || []).catch(() => []);
  const [programs, foodbanks] = await Promise.all([
    readFile(path.join(manual, 'programs.yaml'), 'utf8').then((text) => YAML.parse(text) || []),
    readFile(path.join(manual, 'foodbanks.yaml'), 'utf8').then((text) => YAML.parse(text) || []),
  ]);
  const places = await readFile(placesPath, 'utf8')
    .then((text) => JSON.parse(text))
    .catch((error) => {
      if (error.code === 'ENOENT') return {};
      throw error;
    });
  return { sources, events, programs, foodbanks, directories, places, hasAutoEvents: events.length > 0 };
}
