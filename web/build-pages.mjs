import './build.mjs';
import { build } from 'esbuild';
import { cp, rm, mkdir, writeFile } from 'node:fs/promises';
await rm('pages-dist', { recursive: true, force: true });
await mkdir('pages-dist', { recursive: true });
await cp('public', 'pages-dist', { recursive: true });
await build({ entryPoints: ['src/worker.js'], bundle: true, format: 'esm', platform: 'browser', target: 'es2022', outfile: 'pages-dist/_worker.js', minify: true });
await writeFile('pages-dist/_routes.json', JSON.stringify({ version: 1, include: ['/*'], exclude: [] }, null, 2));
console.log('Built dashboard-uploadable Cloudflare Pages app in pages-dist/');
