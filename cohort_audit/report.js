'use strict';
(() => {
  const data = JSON.parse(document.getElementById('audit-data').textContent);
  const $ = id => document.getElementById(id);
  const make = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
  const pct = x => x === null ? 'unavailable' : (100 * x).toFixed(1) + '%';
  const pp = x => x === null ? 'unavailable' : (x > 0 ? '+' : '') + (100 * x).toFixed(1);
  const name = g => `${g.cohort_id} · ${g.year}`;
  const option = (select, value, text) => { const o = make('option', text); o.value = value; select.append(o); };
  const cell = (row, text) => row.append(make('td', text));
  let page = 0, filtered = [];
  $('notice').textContent = data.notice;
  $('diagnostics').textContent = `${data.diagnostics.input_project_rows} input rows · ${data.diagnostics.duplicate_rows_collapsed} exact duplicates collapsed · ${data.diagnostics.unique_projects} distinct project IDs across all years.`;
  $('normalization').textContent = `Alias mapping ${data.normalization.version}. Labels use NFC normalization, trimming, and case folding, followed by an explicit alias lookup. Unknown labels remain separate. Complete annotations refer to the supplied label list, not verified technology use.`;
  $('hashes').textContent = JSON.stringify(data.provenance, null, 2);
  for (const id of ['before', 'after', 'evidence-group']) for (const g of data.groups) option($(id), g.group_id, name(g));
  $('after').value = String((data.groups.find(g => g.cohort_id === data.groups[0].cohort_id && g.year > data.groups[0].year) || data.groups[1] || data.groups[0]).group_id);
  option($('evidence-tech'), '', 'All technologies');
  for (const t of data.technologies) { option($('evidence-tech'), t, t); option($('composition-tech'), t, t); }
  if (data.technologies.includes('python')) $('composition-tech').value = 'python';
  function summaryCard(g, side) {
    const c = make('div'); c.className = 'card';
    c.append(make('h3', `${side}: ${name(g)}`), make('strong', `${g.summary.projects} projects`),
      make('p', `${g.summary.complete} complete · ${g.summary.partial} partial · ${g.summary.unknown} unknown`),
      make('p', `${g.events.length} event series · ${g.cross_event_excess} cross-event excess records`));
    return c;
  }
  function rates(g, t) {
    const s = g.summary, x = s.technologies[t];
    return `${x.mentions}/${s.projects} (${pct(x.proportion)}); complete-only ${x.complete_mentions}/${s.complete} (${pct(x.complete_proportion)}); possible range ${pct(x.proportion)}–${pct(x.possible_upper)}`;
  }
  function update() {
    const b = data.groups[+$('before').value], a = data.groups[+$('after').value];
    const comparison = data.comparisons.find(c => c.before === Math.min(b.group_id, a.group_id) && c.after === Math.max(b.group_id, a.group_id));
    const direction = b.group_id < a.group_id ? 1 : -1;
    $('coverage').replaceChildren(summaryCard(b, 'Before'), summaryCard(a, 'After'));
    const tbody = $('trends').tBodies[0]; tbody.replaceChildren();
    const visible = data.technologies.filter(t => t.toLowerCase().includes($('filter').value.toLowerCase()));
    for (const t of visible) {
      const row = make('tr'), button = make('button', t); button.className = 'tech';
      button.addEventListener('click', () => { $('evidence-tech').value = t; $('evidence-group').value = a.group_id; $('evidence-mode').value = 'mentions'; page = 0; evidence(); $('composition-tech').value = t; update(); $('evidence-tech').focus(); });
      const td = make('td'); td.append(button); row.append(td); cell(row, rates(b, t)); cell(row, rates(a, t));
      const delta = comparison?.technologies[t];
      const value = key => delta ? (delta[key] === null ? null : direction * delta[key]) : (b.summary.projects ? 0 : null);
      cell(row, pp(value('delta'))); cell(row, pp(value('common_delta'))); cell(row, pp(value('equal_event_delta')));
      cell(row, delta?.reversal ? 'Composition reversal: aggregate and every nonempty shared event move in opposite directions.' : 'Check coverage and annotation gaps.'); tbody.append(row);
    }
    $('trend-status').textContent = `${visible.length} of ${data.technologies.length} technologies shown.`;
    if (comparison) {
      const bs = direction === 1 ? comparison.before_common : comparison.after_common;
      const as = direction === 1 ? comparison.after_common : comparison.before_common;
      $('common-note').textContent = `Shared series: ${comparison.common_events.join(', ') || 'none'}. Nonempty on both sides: ${comparison.nonempty_common_events.join(', ') || 'none'}. Common pooled denominators: ${bs.projects} before / ${as.projects} after; complete: ${bs.complete} / ${as.complete}; partial: ${bs.partial} / ${as.partial}; unknown: ${bs.unknown} / ${as.unknown}. ${comparison.overlapping_project_ids.length} project IDs overlap between selected cohorts. Equal weighting excludes empty sides.`;
    } else $('common-note').textContent = 'Same cohort selected on both sides. No independent comparison.';
    const comp = $('composition').tBodies[0]; comp.replaceChildren();
    for (const [g, side] of [[b, 'Before'], [a, 'After']]) for (const e of g.events) {
      const row = make('tr'), s = e.summary; cell(row, side); cell(row, `${e.event_id} / ${g.year}`);
      cell(row, `${s.projects} / ${e.expected_projects === null ? 'unknown' : e.expected_projects}`);
      cell(row, pct(e.coverage)); cell(row, `${s.complete} / ${s.partial} / ${s.unknown}`);
      cell(row, pct(g.summary.event_records ? s.event_records / g.summary.event_records : null));
      const tech = $('composition-tech').value; cell(row, tech ? `${tech}: ${rates({summary:s}, tech)}` : 'No technologies supplied'); comp.append(row);
    }
  }
  function evidence() {
    const group = data.groups[+$('evidence-group').value], tech = $('evidence-tech').value;
    filtered = group.record_ids.map(i => data.records[i]).filter(r => $('evidence-mode').value === 'all' || (tech ? r.technologies.includes(tech) : r.technologies.length > 0));
    page = Math.min(page, Math.max(0, Math.ceil(filtered.length / 25) - 1));
    const start = page * 25, shown = filtered.slice(start, start + 25);
    $('evidence-status').textContent = `${filtered.length ? start + 1 : 0}–${start + shown.length} of ${filtered.length} evidence records. Page ${page + 1} of ${Math.max(1, Math.ceil(filtered.length / 25))}.`;
    $('evidence').replaceChildren();
    for (const r of shown) {
      const article = make('article'); article.append(make('h3', `${r.project_id} · ${r.title}`), make('p', `${r.event_id} / ${r.year} · ${r.annotation_status} · input records ${r.input_rows.join(', ')}`),
        make('p', `Original: ${JSON.stringify(r.original_labels)}`), make('p', `Normalized: ${r.technologies.join(', ') || '(no labels supplied)'}`));
      const a = make('a', r.source_url); a.href = r.source_url; a.target = '_blank'; a.rel = 'noopener noreferrer'; article.append(a); $('evidence').append(article);
    }
    $('previous').disabled = page === 0; $('next').disabled = start + 25 >= filtered.length;
  }
  function download(value, filename) {
    const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], {type:'application/json'}), url = URL.createObjectURL(blob);
    const a = make('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  for (const id of ['before', 'after']) $(id).addEventListener('change', update);
  $('filter').addEventListener('input', update);
  $('composition-tech').addEventListener('change', update);
  for (const id of ['evidence-group', 'evidence-tech', 'evidence-mode']) $(id).addEventListener('change', () => {page = 0; evidence();});
  $('previous').addEventListener('click', () => {page--; evidence();});
  $('next').addEventListener('click', () => {page++; evidence();});
  $('download').addEventListener('click', () => download(data, 'cohort-audit.json'));
  $('download-evidence').addEventListener('click', () => download({group:data.groups[+$('evidence-group').value].cohort_id, year:data.groups[+$('evidence-group').value].year, technology:$('evidence-tech').value, mode:$('evidence-mode').value, records:filtered}, 'cohort-evidence.json'));
  update(); evidence();
})();
