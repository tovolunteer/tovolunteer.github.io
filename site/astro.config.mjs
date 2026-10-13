import { defineConfig } from 'astro/config';

const requestedBase = process.env.SITE_BASE ?? '/';
const trimmed = requestedBase.replace(/^\/+|\/+$/g, '');
const base = trimmed ? `/${trimmed}/` : '/';

export default defineConfig({
  base,
  output: 'static',
  trailingSlash: 'always',
});
