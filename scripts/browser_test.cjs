/* Real Chromium, file:// reports, external network blocked. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({headless:true, args:['--disable-background-networking']});
  const context = await browser.newContext({acceptDownloads:true, viewport:{width:1280,height:900}, serviceWorkers:'block', offline:true});
  const attempts = [], errors = [];
  await context.route(/^https?:/, route => {attempts.push(route.request().url()); return route.abort('blockedbyclient');});
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  try {
    await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    await page.locator('#trends tbody tr').first().waitFor();
    const data = await page.locator('#audit-data').textContent().then(JSON.parse);
    const group = (cohort, year) => String(data.groups.find(g => g.cohort_id === cohort && g.year === year).group_id);
    const before = group('synthetic-reversal', 2024), after = group('synthetic-reversal', 2025);
    assert.equal(await page.locator('#before').inputValue(), before);
    assert.equal(await page.locator('#after').inputValue(), after);
    await page.locator('#filter').fill('PyThOn');
    assert.equal(await page.locator('#trends tbody tr').count(), 1);
    const trend = await page.locator('#trends tbody tr').innerText();
    for (const value of ['74/100', '36/100', '-38.0', '+10.0', 'Composition reversal']) assert.ok(trend.includes(value), trend);
    const composition = await page.locator('#composition').innerText();
    for (const value of ['72/90', '2/10', '9/10', '27/90']) assert.ok(composition.includes(value));
    // Keyboard-only activation of the technology evidence drill-down.
    await page.getByRole('button', {name:'python', exact:true}).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#evidence-tech').inputValue(), 'python');
    assert.equal(await page.locator('#evidence-group').inputValue(), after);
    assert.equal(await page.locator('#evidence article').count(), 25);
    assert.ok((await page.locator('#evidence-status').innerText()).includes('of 36'));
    await page.locator('#next').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('#evidence article').count(), 11);
    assert.ok(await page.locator('#next').isDisabled());
    await page.locator('#previous').click();
    assert.equal(await page.locator('#evidence article').count(), 25);
    await page.locator('#evidence-mode').selectOption('all');
    const seen = new Set();
    while (true) {
      for (const text of await page.locator('#evidence h3').allTextContents()) seen.add(text);
      assert.ok(await page.locator('#evidence article').count() <= 25);
      if (await page.locator('#next').isDisabled()) break;
      await page.locator('#next').click();
    }
    assert.equal(seen.size, 100, 'all records reachable by pagination');
    // Downloads preserve all evidence, not only mounted rows.
    let pending = page.waitForEvent('download'); await page.locator('#download-evidence').click();
    let downloaded = await pending;
    const evidence = JSON.parse(fs.readFileSync(await downloaded.path(), 'utf8'));
    assert.equal(evidence.records.length, 100);
    pending = page.waitForEvent('download'); await page.locator('#download').click(); downloaded = await pending;
    assert.deepEqual(JSON.parse(fs.readFileSync(await downloaded.path(), 'utf8')), data);
    // Reversed selectors reverse changes; same-cohort and empty data remain honest.
    await page.locator('#before').selectOption(after); await page.locator('#after').selectOption(before);
    assert.ok((await page.locator('#trends tbody tr').innerText()).includes('+38.0'));
    await page.locator('#after').selectOption(after);
    assert.ok((await page.locator('#common-note').innerText()).includes('Same cohort'));
    const empty = group('synthetic-empty', 2025);
    await page.locator('#after').selectOption(empty);
    assert.ok((await page.locator('#trends tbody tr').innerText()).includes('unavailable'));
    await page.locator('#evidence-group').selectOption(empty);
    assert.equal(await page.locator('#evidence article').count(), 0);
    assert.ok(await page.locator('#previous').isDisabled()); assert.ok(await page.locator('#next').isDisabled());
    await page.locator('#filter').fill('nonexistent');
    assert.equal(await page.locator('#trends tbody tr').count(), 0);
    // Imported HTML stays literal even when visible in labels and evidence.
    await page.locator('#filter').fill('');
    const hostile = data.technologies.find(t => t.startsWith('</script>'));
    const coverage = group('synthetic-coverage', 2025);
    await page.locator('#evidence-group').selectOption(coverage);
    await page.locator('#evidence-tech').selectOption(hostile);
    await page.locator('#evidence-mode').selectOption('mentions');
    assert.equal(await page.locator('#evidence article').count(), 1);
    assert.ok((await page.locator('#evidence').innerText()).includes('</script><img'));
    assert.equal(await page.locator('img').count(), 0);
    assert.equal(await page.evaluate(() => window.pwned), undefined);
    assert.equal(await page.locator('#evidence a').getAttribute('rel'), 'noopener noreferrer');
    assert.equal(await page.locator('#evidence a').getAttribute('href'), 'https://example.invalid/projects/shared');
    // Native keyboard selection, tab navigation, and narrow viewport layout.
    await page.locator('#evidence-group').focus();
    await page.keyboard.press('ArrowDown'); await page.keyboard.press('Escape');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'evidence-tech');
    await page.setViewportSize({width:360,height:740});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.ok(await page.locator('#filter').isVisible());
    if (process.argv[3]) await page.screenshot({path:process.argv[3], fullPage:true});
    // Second fixture: completely empty input still renders and downloads.
    if (process.argv[4]) {
      await page.goto(pathToFileURL(path.resolve(process.argv[4])).href);
      await page.locator('#coverage .card').first().waitFor();
      assert.equal(await page.locator('#trends tbody tr').count(), 0);
      assert.ok((await page.locator('#trend-status').innerText()).includes('0 of 0'));
      assert.equal(await page.locator('#evidence article').count(), 0);
    }
    assert.deepEqual(attempts, [], 'report must not attempt external requests');
    assert.deepEqual(errors, [], 'no JS or CSP errors');
    console.log(JSON.stringify({status:'passed', browser:await browser.version(), assertions:'filters, before/after, event rates, pagination, downloads, keyboard, empty data, hostile text, 360px viewport', external_requests:attempts.length, errors}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
