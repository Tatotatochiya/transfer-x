// measure-type.mjs — how big is the text TransferX actually renders?
//
// Usage (local stack running, demo data seeded):
//   node frontend/scripts/measure-type.mjs http://127.0.0.1:5173 club@example.com 'password'
//
// Signs in once per viewport, visits each route, and for the visible text inside <main>
// reports: h1 size/weight, dominant body size, % of characters under 13px, and every size
// on screen. Writes the full result to type-measure.json in the current directory.
// Pages that need an id (offer, deal, player, club) are reached by following the first
// matching link on their list page, so no ids are hard-coded.

import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';

const [BASE = 'http://127.0.0.1:5173', EMAIL, PASSWORD] = process.argv.slice(2);
if (!EMAIL || !PASSWORD) {
  console.error('usage: node measure-type.mjs <base-url> <email> <password>');
  process.exit(1);
}

const VIEWPORTS = [
  ['phone', 390, 844],
  ['laptop', 1280, 790],
];

// [name, path] or [name, listPath, linkSelector] to follow the first matching link.
const ROUTES = [
  ['Dashboard', '/dashboard'],
  ['Browse Players', '/players/market'],
  ['Player', '/players/market', 'main a[href^="/players/market/"]'],
  ['Offer', '/offers/received', 'main a[href^="/offers/"]:not([href$="/new"])'],
  ['Deal', '/deals', 'main a[href^="/deals/"]'],
  ['Board', '/board'],
  ['My Club', '/club'],
  ['Finance', '/club/finance'],
  ['Transfers', '/transfers'],
  ['Clubs', '/clubs'],
  ['Club', '/clubs', 'main a[href^="/clubs/"]'],
  ['Listings', '/sales'],
  ['Notifications', '/notifications'],
  ['Account', '/account'],
  ['Make an offer', '/offers/new'],
  ['Ask', '/ask'],
  ['Lite', '/lite'],
];

async function settle(page, url) {
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  } catch {
    /* slow page: measure what rendered */
  }
  await page.waitForTimeout(1200);
}

function measure() {
  const root = document.querySelector('main') || document.body;
  const hist = {};
  const small = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const t = n.textContent.trim();
    if (!t) continue;
    const el = n.parentElement;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || el.getClientRects().length === 0) continue;
    const fs = Math.round(parseFloat(cs.fontSize) * 10) / 10;
    const key = fs + '/' + cs.fontWeight;
    hist[key] = (hist[key] || 0) + t.length;
    if (fs < 13 && small.length < 10) small.push(fs + 'px ' + t.slice(0, 40));
  }
  const sizes = {};
  for (const k in hist) {
    const s = k.split('/')[0];
    sizes[s] = (sizes[s] || 0) + hist[k];
  }
  const total = Object.values(sizes).reduce((a, b) => a + b, 0);
  const below13 = Object.entries(sizes)
    .filter(([s]) => +s < 13)
    .reduce((a, [, c]) => a + c, 0);
  const atLeast15 = Object.entries(sizes)
    .filter(([s]) => +s >= 15)
    .reduce((a, [, c]) => a + c, 0);
  const body = {};
  for (const k in hist) {
    const [s, wt] = k.split('/');
    if (+wt <= 500) body[s] = (body[s] || 0) + hist[k];
  }
  const bodySize = Object.entries(body).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
  const h1 = document.querySelector('h1');
  const h1s = h1 ? getComputedStyle(h1) : null;
  return {
    h1: h1 ? { text: h1.textContent.trim().slice(0, 30), size: h1s.fontSize, weight: h1s.fontWeight } : null,
    sizesOnScreen: Object.keys(sizes).sort((a, b) => a - b),
    pctBelow13: total ? Math.round((100 * below13) / total) : 0,
    pctAtLeast15: total ? Math.round((100 * atLeast15) / total) : 0,
    bodySize,
    chars: total,
    sampleUnder13: small,
  };
}

const browser = await chromium.launch();
const out = {};
let failures = 0;

for (const [vName, width, height] of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/login');
  await page.fill('#email', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await page.waitForTimeout(2000);

  for (const [name, path, follow] of ROUTES) {
    await settle(page, BASE + path);
    if (follow) {
      const href = await page.locator(follow).first().getAttribute('href').catch(() => null);
      if (!href) {
        console.log(vName.padEnd(7), name.padEnd(15), 'skipped: no link matching', follow);
        continue;
      }
      await settle(page, BASE + href);
    }
    const r = await page.evaluate(measure);
    out[`${vName}:${name}`] = { url: page.url(), ...r };
    const over = r.sizesOnScreen.length > 6;
    const under = r.pctBelow13 > 0;
    if (under || over) failures++;
    console.log(
      vName.padEnd(7),
      name.padEnd(15),
      'h1',
      (r.h1 ? `${r.h1.size}/${r.h1.weight}` : 'none').padEnd(9),
      '| body',
      String(r.bodySize).padEnd(4),
      '| <13px',
      String(r.pctBelow13 + '%').padEnd(4),
      '| ≥15px',
      String(r.pctAtLeast15 + '%').padEnd(4),
      '| sizes',
      r.sizesOnScreen.join(','),
      under || over ? '  ✗' : '  ✓',
    );
  }
  await ctx.close();
}

writeFileSync('type-measure.json', JSON.stringify(out, null, 1));
await browser.close();
console.log(`\n${failures} page/viewport(s) miss the target (0% under 13px, ≤ 6 sizes). Details in type-measure.json`);
