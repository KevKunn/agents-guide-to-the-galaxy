// Usage: node run-repros.mjs --label before|after [--dir findings/A[,findings/B]] [--id A-03[,B-01]] [--per-tenant 1]
// One browser + one login per tenant/user/module/viewport group; tenants run in parallel.
import * as lib from './sweep-lib.mjs';
import fs from 'fs';
import path from 'path';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a), []));
const label = args.label || 'before';
const perTenant = Math.max(1, +(args['per-tenant'] || 1));
const root = path.join(lib.SWEEP_DIR, 'findings');
const dirs = args.dir
  ? args.dir.split(',').map(d => path.resolve(lib.SWEEP_DIR, d))
  : fs.readdirSync(root, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => path.join(root, d.name));
const ids = args.id ? new Set(args.id.split(',')) : null;

const findings = [];
for (const d of dirs) for (const f of fs.readdirSync(d).filter(f => f.endsWith('.json') && f !== 'coverage.json')) {
  const j = JSON.parse(fs.readFileSync(path.join(d, f), 'utf8'));
  if (j.id && (!ids || ids.has(j.id))) findings.push({ ...j, __dir: d });
}
const groups = {};
for (const f of findings) {
  const vp = f.viewport || lib.VIEWPORTS[0];
  const k = [f.tenant, f.user || 'none', f.module || '', vp.width, vp.height].join('|');
  (groups[k] ||= []).push(f);
}

const total = findings.length;
let done = 0, failed = 0;
const started = Date.now();
const log = (ok, id, ms, info) => {
  done++;
  if (!ok) failed++;
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${id} ${(ms / 1000).toFixed(1)}s [${done}/${total}] ${info}`);
};

async function runGroup(key, list) {
  const [tenant, user, module, w, h] = key.split('|');
  let s;
  try {
    s = await lib.open({ tenant, user, module: module || undefined, width: +w, height: +h });
  } catch (e) {
    for (const f of list) log(false, f.id, 0, 'login: ' + e.message.split('\n')[0]);
    return;
  }
  const { browser, page } = s;
  for (const f of list) {
    const out = path.join(f.__dir, `${f.id}.${label}.png`);
    const t0 = Date.now();
    try {
      const fn = (0, eval)('(' + f.steps + ')');
      await fn(page, lib);
      await lib.settle(page, 800);
      await lib.shot(page, out, { clip: f.clip, marks: f.marks || [], pad: f.pad ?? 16, fullPage: !!f.fullPage });
      log(true, f.id, Date.now() - t0, out);
    } catch (e) {
      log(false, f.id, Date.now() - t0, e.message.split('\n')[0]);
      if (/Target page|closed|crash/i.test(e.message)) {
        for (const rest of list.slice(list.indexOf(f) + 1)) log(false, rest.id, 0, 'skipped after browser crash');
        break;
      }
    }
  }
  await browser.close();
}

const queues = {};
for (const [k, list] of Object.entries(groups)) (queues[k.split('|')[0]] ||= []).push([k, list]);
const workers = [];
for (const queue of Object.values(queues))
  for (let i = 0; i < perTenant; i++)
    workers.push((async () => { for (let next = queue.shift(); next; next = queue.shift()) await runGroup(...next); })());
await Promise.all(workers);
console.log(`done ${done}/${total}, ${failed} failed, ${((Date.now() - started) / 60000).toFixed(1)} min`);
process.exitCode = failed ? 1 : 0;
