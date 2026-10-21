// Usage: node enum-nav.mjs  ->  nav.json { "<tenant>|<user>|<module>": { url, nav: [{ text, href, groups }] } }
import * as lib from './sweep-lib.mjs';
import fs from 'fs';
import path from 'path';

const plan = lib.CONFIG.navPlan || [];
if (!plan.length) throw new Error('sweep.config.json has no navPlan');
const result = {};
await Promise.all(Object.values(plan.reduce((byTenant, p) => ((byTenant[p.tenant] ||= []).push(p), byTenant), {})).map(async list => {
  for (const { tenant, user, modules } of list) for (const module of modules?.length ? modules : ['']) {
    const key = `${tenant}|${user}|${module}`;
    let s;
    try {
      s = await lib.open({ tenant, user, module: module || undefined });
      result[key] = { url: s.page.url(), nav: await lib.navTree(s.page) };
    } catch (e) {
      result[key] = { error: e.message.split('\n')[0], url: s?.page.url() };
    }
    if (s) await s.browser.close();
    console.log(key, result[key].nav?.length ?? result[key].error);
  }
}));
fs.writeFileSync(path.join(lib.SWEEP_DIR, 'nav.json'), JSON.stringify(result, null, 1));
