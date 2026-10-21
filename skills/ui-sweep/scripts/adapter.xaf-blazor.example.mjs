// Example adapter for a DevExpress XAF Blazor app (German UI, password-empty test users, custom module combobox on the login page).
// Copy to <sweep dir>/adapter.mjs and adapt the texts and selectors.

export const busySelectors = ['.xaf-loading', '.dxbl-loading-panel', '.dxbl-wait-indicator'];

export const auditOptions = {
  ignore: '.dxbl-a11y-status-helper',
  rawExtra: '_(ListView|DetailView|LookupListView)$|_(ListView|DetailView)_',
};

// Never types a password: only users with an empty password are supported.
export async function login(page, lib, { tenant, user, module }) {
  await page.goto(lib.url(tenant, 'LoginPage'));
  await page.waitForSelector('input.dxbl-text-edit-input', { timeout: 90000 });
  await page.waitForTimeout(800);
  await page.locator('input.dxbl-text-edit-input[type=text]:not([role=combobox])').first().fill(user);
  if (module) {
    const combo = page.locator('input[role=combobox]').first();
    if ((await combo.inputValue()) !== module) {
      await page.locator('.dxbl-edit-btn-dropdown').first().click();
      await page.locator('[role=listbox] [role=option]').filter({ hasText: new RegExp('^' + module + '$') }).first().click();
      await page.waitForTimeout(500);
    }
  }
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
  await page.waitForURL(u => !/LoginPage/i.test(u.toString()), { timeout: 90000 });
  await lib.settle(page, 2500);
}

export async function isLoggedIn(page) {
  return !/LoginPage/i.test(page.url());
}

export async function goView(page, lib, tenant, route) {
  await page.goto(lib.url(tenant, route));
  await lib.settle(page);
}

export async function expandNav(page) {
  await page.waitForSelector('.dxbl-accordion-group-header', { timeout: 30000 }).catch(() => {});
  for (let i = 0; i < 40; i++) {
    const h = page.locator('.dxbl-accordion-group-header[aria-expanded=false] .dxbl-group-expand-btn').first();
    if (!(await h.count())) break;
    await h.evaluate(e => e.click());
    await page.waitForTimeout(400);
  }
}

export async function navTree(page, lib) {
  await expandNav(page, lib);
  return page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.dxbl-accordion-items-container a[href]').forEach(a => {
      const groups = [];
      for (let el = a.parentElement; el && el !== document.body; el = el.parentElement) {
        if (el.matches('dxbl-group-control.dxbl-accordion-item, .dxbl-accordion-item.has-children')) {
          const t = el.querySelector(':scope > .dxbl-accordion-group-header .xaf-nav-link');
          if (t) groups.unshift(t.innerText.trim());
        }
      }
      out.push({ text: a.innerText.trim(), href: a.getAttribute('href'), groups: groups.join(' / ') });
    });
    return out;
  });
}
