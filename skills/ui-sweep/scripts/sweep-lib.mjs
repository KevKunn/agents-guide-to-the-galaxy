import { createRequire } from 'module';
import { execSync } from 'child_process';
import { fileURLToPath, pathToFileURL } from 'url';
import fs from 'fs';
import path from 'path';

export const SWEEP_DIR = (process.env.SWEEP_DIR || path.dirname(fileURLToPath(import.meta.url))).replace(/\\/g, '/');
export const CONFIG = JSON.parse(fs.readFileSync(path.join(SWEEP_DIR, 'sweep.config.json'), 'utf8'));
export const TENANTS = Object.fromEntries(Object.entries(CONFIG.tenants).map(([k, v]) => [k, typeof v === 'string' ? v : v.url]));
export const VIEWPORTS = CONFIG.viewports?.length ? CONFIG.viewports : [{ width: 1600, height: 900 }, { width: 1280, height: 720 }];

function loadPlaywright() {
  const dirs = [CONFIG.playwrightFrom && path.resolve(SWEEP_DIR, CONFIG.playwrightFrom), SWEEP_DIR];
  try { dirs.push(path.join(execSync('npm root -g', { encoding: 'utf8' }).trim(), '@playwright', 'cli')); } catch {}
  const missing = [];
  for (const d of dirs.filter(Boolean)) {
    let pw;
    try { pw = createRequire(path.join(d, 'noop.js'))('playwright'); } catch { continue; }
    if (fs.existsSync(pw.chromium.executablePath())) return pw;
    missing.push(`${d} (browser for this Playwright version not installed: ${pw.chromium.executablePath()})`);
  }
  throw new Error('no usable playwright: set "playwrightFrom" in sweep.config.json to a folder whose node_modules has playwright with its browsers installed, or run "npx playwright install chromium" for that version.' + (missing.length ? ' Found without browsers: ' + missing.join('; ') : ''));
}
export const { chromium } = loadPlaywright();

const adapterPath = path.resolve(SWEEP_DIR, CONFIG.adapter || './adapter.mjs');
export const adapter = await import(pathToFileURL(adapterPath).href);

export const url = (tenant, route = '') => {
  if (!TENANTS[tenant]) throw new Error(`unknown tenant ${tenant}`);
  return TENANTS[tenant].replace(/\/$/, '') + '/' + String(route).replace(/^\//, '');
};

export async function launch(width = VIEWPORTS[0].width, height = VIEWPORTS[0].height, { storageState } = {}) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width, height }, locale: CONFIG.locale || 'en-US', deviceScaleFactor: 1, storageState });
  const page = await context.newPage();
  const failRe = new RegExp(CONFIG.failedRequestPattern || '\\.(svg|png|gif|jpe?g|webp|ico)(\\?|$)', 'i');
  page.__failedImages = [];
  page.__consoleErrors = [];
  page.on('response', r => { if (r.status() >= 400 && failRe.test(r.url())) page.__failedImages.push(`${r.status()} ${r.url()}`); });
  page.on('console', m => { if (m.type() === 'error') page.__consoleErrors.push(m.text().slice(0, 300)); });
  return { browser, context, page };
}

export async function settle(page, ms = CONFIG.settleMs ?? 1500) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  const busy = adapter.busySelectors || [];
  if (busy.length)
    await page.waitForFunction(sels => !sels.some(s => [...document.querySelectorAll(s)].some(e => e.getClientRects().length)), busy, { timeout: 30000 }).catch(() => {});
  if (adapter.ready) await adapter.ready(page, lib).catch(() => {});
  await page.waitForTimeout(ms);
}

export async function login(page, tenant, user, module) {
  if (!user || user === 'none') return;
  await adapter.login(page, lib, { tenant, user, module: module || undefined });
}

const authFile = (tenant, user, module, w, h) =>
  path.join(SWEEP_DIR, '.auth', [tenant, user, module || '', w, h].join('_').replace(/[^\w.-]+/g, '_') + '.json');

export async function open({ tenant, user, module, width = VIEWPORTS[0].width, height = VIEWPORTS[0].height }) {
  const reuse = CONFIG.reuseStorageState && user && user !== 'none';
  const file = authFile(tenant, user, module, width, height);
  if (reuse && fs.existsSync(file)) {
    const s = await launch(width, height, { storageState: file });
    await goView(s.page, tenant, '');
    if (!adapter.isLoggedIn || await adapter.isLoggedIn(s.page, lib)) return s;
    await s.browser.close();
  }
  const s = await launch(width, height);
  try { await login(s.page, tenant, user, module); } catch (e) { await s.browser.close(); throw e; }
  if (reuse) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    await s.context.storageState({ path: file });
  }
  return s;
}

export async function goView(page, tenant, route) {
  if (adapter.goView) return adapter.goView(page, lib, tenant, route);
  await page.goto(url(tenant, route));
  await settle(page);
}

export async function expandNav(page) {
  if (adapter.expandNav) await adapter.expandNav(page, lib);
}

export async function navTree(page) {
  if (!adapter.navTree) throw new Error('adapter has no navTree');
  return adapter.navTree(page, lib);
}

const DEFAULT_FOREIGN = '\\b(the|and|or|of|Add|Delete|Save|Close|New|Edit|Refresh|Search|Cancel|Yes|No|Show|Hide|Export|Columns?|Group|Clear|Apply|Loading|Error|Log ?Off|Log ?In|Settings|Items?|Page|Rows?|Select|Choose|Drag|Drop|Here|Sort|Ascending|Descending|Today|Records?|Total|Count|Sum|Value|Description|Type|Date|Created|Modified|Owner|Role|View|Open|Print|Download|Upload|Reset|Undo|Redo|Link|Unlink|Back|Next|Previous|First|Last|Warning|Information|Success|Failed|Required|Empty|None|All|Other|Customize|Expand|Collapse)\\b';
const DEFAULT_RAW = '^(N\\/A|null|undefined|NaN|\\[object Object\\])$|\\{\\d+(:[^}]*)?\\}|^Auto[0-9a-f]{8}-|^[a-z]+[A-Z][A-Za-z]+$|^[A-Z][a-z]+[A-Z][a-z]+[A-Za-z]*$';

const auditInPage = (scope, o) => {
  const root = document.querySelector(scope) || document.body;
  const foreignRe = o.foreign ? new RegExp(o.foreign) : null, rawRe = new RegExp(o.raw);
  const vis = e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 2 && r.height > 2 && !(o.ignore && e.matches(o.ignore)) && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0'; };
  const sel = e => { const p = []; let n = e; for (let i = 0; n && n.nodeType === 1 && i < 5; i++, n = n.parentElement) { let s = n.tagName.toLowerCase(); if (n.id && !/^id[0-9a-f-]{20,}/.test(n.id)) { s += '#' + n.id; p.unshift(s); break; } const c = [...n.classList].filter(c => !/[0-9a-f-]{20,}/.test(c)).slice(0, 3); if (c.length) s += '.' + c.join('.'); p.unshift(s); } return p.join(' > '); };
  const rect = e => { const r = e.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
  const ownText = e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
  const textRect = e => { const tn = [...e.childNodes].find(n => n.nodeType === 3 && n.textContent.trim()); const rg = document.createRange(); rg.selectNodeContents(tn); return rg.getBoundingClientRect(); };
  const out = { truncated: [], clippedVertical: [], brokenImages: [], tightPadding: [], foreignLanguageCandidates: [], emptyButtons: [], overlaps: [], rawOrPlaceholder: [] };
  const all = [...root.querySelectorAll('*')].filter(e => !e.closest('.__sweep_mark') && vis(e));
  for (const e of all) {
    const cs = getComputedStyle(e);
    const txt = (e.innerText || '').trim();
    const ot = ownText(e);
    if (ot) {
      const tr = textRect(e);
      if (cs.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1)
        out.truncated.push({ kind: 'ellipsis', sel: sel(e), text: ot.slice(0, 120), title: e.getAttribute('title') || '', scrollW: e.scrollWidth, clientW: e.clientWidth, rect: rect(e) });
      else {
        let anc = e;
        for (let i = 0; anc && i < 7; i++, anc = anc.parentElement) {
          const acs = getComputedStyle(anc);
          const ar = anc.getBoundingClientRect();
          if (acs.textOverflow === 'ellipsis' && anc.scrollWidth > anc.clientWidth + 1) { out.truncated.push({ kind: 'ellipsis-ancestor', sel: sel(e), text: ot.slice(0, 120), title: anc.getAttribute('title') || '', scrollW: anc.scrollWidth, clientW: anc.clientWidth, rect: rect(anc) }); break; }
          const clipX = acs.overflowX === 'hidden' || acs.overflowX === 'clip', clipY = acs.overflowY === 'hidden' || acs.overflowY === 'clip';
          if (clipX && (tr.right > ar.right + 1 || tr.left < ar.left - 1)) { out.truncated.push({ kind: 'clipped', sel: sel(e), text: ot.slice(0, 120), textW: Math.round(tr.width), visibleW: Math.round(Math.min(tr.right, ar.right) - Math.max(tr.left, ar.left)), rect: rect(anc) }); break; }
          if (clipY && (tr.bottom > ar.bottom + 1 || tr.top < ar.top - 1)) { out.clippedVertical.push({ sel: sel(e), text: ot.slice(0, 120), textH: Math.round(tr.height), visibleH: Math.round(Math.min(tr.bottom, ar.bottom) - Math.max(tr.top, ar.top)), rect: rect(anc) }); break; }
          if (acs.overflowX === 'auto' || acs.overflowX === 'scroll') break;
        }
      }
      const bw = ['Left', 'Right', 'Top', 'Bottom'].map(s => parseFloat(cs['border' + s + 'Width']) > 0 && cs['border' + s + 'Style'] !== 'none');
      const hasBg = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent';
      if (bw.some(Boolean) || hasBg) {
        const er = e.getBoundingClientRect();
        const gapL = Math.round(tr.left - er.left - parseFloat(cs.borderLeftWidth)), gapR = Math.round(er.right - tr.right - parseFloat(cs.borderRightWidth));
        if (Math.min(gapL, gapR) < 3) out.tightPadding.push({ sel: sel(e), text: ot.slice(0, 80), gapLeft: gapL, gapRight: gapR, padding: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(' '), border: bw, background: hasBg ? cs.backgroundColor : null, rect: rect(e) });
      }
      if (rawRe.test(ot)) out.rawOrPlaceholder.push({ sel: sel(e), text: ot.slice(0, 120), rect: rect(e) });
      if (foreignRe && foreignRe.test(ot)) out.foreignLanguageCandidates.push({ sel: sel(e), text: ot.slice(0, 120), rect: rect(e) });
    }
    if ((e.tagName === 'BUTTON' || e.getAttribute('role') === 'button') && !txt && !e.getAttribute('title') && !e.getAttribute('aria-label') && !e.querySelector('svg, img, [class*=image], [class*=icon]'))
      out.emptyButtons.push({ sel: sel(e), rect: rect(e) });
  }
  for (const img of root.querySelectorAll('img')) if (vis(img) && img.complete && img.naturalWidth === 0) out.brokenImages.push({ sel: sel(img), src: img.getAttribute('src'), rect: rect(img) });
  for (const s of root.querySelectorAll('svg')) if (vis(s) && !s.querySelector('path,use,rect,circle,polygon,g,line,image,ellipse,polyline')) out.brokenImages.push({ sel: sel(s), src: '(empty svg)', rect: rect(s) });
  const leafs = all.filter(e => ownText(e) && e.children.length === 0).slice(0, 2500);
  for (let i = 0; i < leafs.length; i++) for (let j = i + 1; j < Math.min(leafs.length, i + 40); j++) {
    const a = leafs[i].getBoundingClientRect(), b = leafs[j].getBoundingClientRect();
    const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ox > 2 && oy > 2) out.overlaps.push({ a: sel(leafs[i]), aText: ownText(leafs[i]).slice(0, 60), b: sel(leafs[j]), bText: ownText(leafs[j]).slice(0, 60), overlapPx: [Math.round(ox), Math.round(oy)] });
  }
  for (const k of Object.keys(out)) out[k] = out[k].slice(0, 60);
  return out;
};

export async function audit(page, scope = 'body') {
  const a = { ...(adapter.auditOptions || {}), ...(CONFIG.audit || {}) };
  const raw = [DEFAULT_RAW, adapter.auditOptions?.rawExtra, CONFIG.audit?.rawExtra].filter(Boolean).join('|');
  const opts = { ignore: a.ignore || '', foreign: a.foreignWords === undefined ? DEFAULT_FOREIGN : a.foreignWords, raw };
  const res = JSON.parse(await page.evaluate(([src, scope, opts]) => JSON.stringify((0, eval)('(' + src + ')')(scope, opts)), [auditInPage.toString(), scope, opts]));
  res.failedImageRequests = [...new Set(page.__failedImages)];
  res.consoleErrors = [...new Set(page.__consoleErrors)].slice(0, 20);
  page.__failedImages.length = 0; page.__consoleErrors.length = 0;
  return res;
}

export async function shot(page, file, { clip, marks = [], pad = 16, fullPage = false } = {}) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  await page.evaluate((marks) => {
    for (const m of marks) {
      const rects = typeof m === 'string' ? [...document.querySelectorAll(m)].slice(0, 20).map(e => e.getBoundingClientRect()) : [{ left: m.x, top: m.y, width: m.w, height: m.h }];
      for (const r of rects) {
        const d = document.createElement('div'); d.className = '__sweep_mark';
        Object.assign(d.style, { position: 'fixed', left: (r.left - 2) + 'px', top: (r.top - 2) + 'px', width: (r.width + 4) + 'px', height: (r.height + 4) + 'px', outline: '2px solid #e00', zIndex: 2147483647, pointerEvents: 'none' });
        document.body.appendChild(d);
      }
    }
  }, marks);
  const opts = { path: file, fullPage };
  if (clip) {
    const r = typeof clip === 'string' ? await page.locator(clip).first().boundingBox() : { x: clip.x, y: clip.y, width: clip.width ?? clip.w, height: clip.height ?? clip.h };
    if (r) {
      const vp = page.viewportSize();
      const x = Math.max(0, r.x - pad), y = Math.max(0, r.y - pad);
      opts.clip = { x, y, width: Math.min(vp.width - x, r.width + 2 * pad), height: Math.min(vp.height - y, r.height + 2 * pad) };
    }
  }
  await page.screenshot(opts);
  await page.evaluate(() => document.querySelectorAll('.__sweep_mark').forEach(e => e.remove()));
  return file;
}

export const lib = { SWEEP_DIR, CONFIG, TENANTS, VIEWPORTS, chromium, adapter, url, launch, settle, login, open, goView, expandNav, navTree, audit, shot };
