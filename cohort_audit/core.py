"""Strict input contract and deterministic project-level descriptive statistics."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

LIMITS = dict(input_bytes=4 * 1024 * 1024, project_rows=5000, cohort_rows=128,
              groups=16, technologies=64, labels_per_record=32, label_chars=100,
              text_chars=1000, field_chars=8000, operations=2_000_000,
              json_bytes=8 * 1024 * 1024, html_bytes=10 * 1024 * 1024,
              runtime_seconds=30)
PROJECT_FIELDS = ['project_id', 'event_id', 'year', 'title', 'source_url',
                  'technologies', 'annotation_status']
COHORT_FIELDS = ['cohort_id', 'event_id', 'year', 'expected_projects']
NOTICE = ('Descriptive mentions in supplied records only; not verified technology use, '
          'population trends, or causal effects. Missing labels do not establish non-use. '
          'Common-event comparisons do not remove selection or annotation bias.')

class AuditError(ValueError):
    pass

class Budget:
    def __init__(self, seconds=30):
        self.deadline = time.monotonic() + seconds
        self.operations = 0

    def check(self, operations=0):
        self.operations += operations
        if self.operations > LIMITS['operations']:
            raise AuditError('computation limit exceeded')
        if time.monotonic() > self.deadline:
            raise AuditError('runtime limit exceeded')


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False) + '\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path, budget):
    # Reject devices/FIFOs before opening: they can block indefinitely.
    path = Path(path)
    if not path.is_file():
        raise AuditError('input must be a regular file')
    with path.open('rb') as stream:
        raw = stream.read(LIMITS['input_bytes'] + 1)
    budget.check()
    if len(raw) > LIMITS['input_bytes']:
        raise AuditError('input byte limit exceeded')
    return raw


def read_csv(raw, fields, maximum, budget):
    if len(raw) > LIMITS['input_bytes']:
        raise AuditError('input byte limit exceeded')
    try:
        text = raw.decode('utf-8-sig')
        if '\x00' in text:
            raise AuditError('NUL bytes are not accepted')
        csv.field_size_limit(LIMITS['field_chars'])
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader, None)
        if header != fields:
            raise AuditError('CSV header must be exactly: ' + ','.join(fields))
        rows = []
        for row in reader:
            budget.check()
            if len(rows) >= maximum:
                raise AuditError('record limit exceeded')
            if len(row) != len(fields):
                raise AuditError(f'CSV record {len(rows) + 2}: incorrect field count')
            if any(len(cell) > LIMITS['field_chars'] for cell in row):
                raise AuditError('field limit exceeded')
            rows.append(dict(zip(fields, row)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise AuditError('invalid UTF-8 or CSV: ' + str(exc)) from exc


def clean_text(value, maximum=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise AuditError('empty or oversized text')
    if any(unicodedata.category(c) in ('Cc', 'Cs') for c in value):
        raise AuditError('control characters are not accepted in text fields')
    return value


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}', value):
        raise AuditError('identifiers must be 1–80 ASCII letters, digits, _, ., :, or -')
    return value


def year_number(value):
    if not re.fullmatch(r'[12][0-9]{3}', value):
        raise AuditError('year must be a four-digit number from 1000 to 2999')
    return int(value)


def label_key(label):
    clean_text(label, LIMITS['label_chars'])
    return unicodedata.normalize('NFC', label).strip().casefold()


def alias_mapping():
    raw = files('cohort_audit').joinpath('aliases.json').read_bytes()
    mapping = json.loads(raw)
    return mapping, digest(raw)


def valid_url(value):
    clean_text(value)
    try:
        url = urlsplit(value)
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username
                or url.password or any(c.isspace() for c in value)
                or any(c in value for c in '\\<>"') or url.port == 0):
            raise ValueError()
    except ValueError as exc:
        raise AuditError('source_url must be an absolute http(s) URL without credentials') from exc
    return value


def load(project_raw, cohort_raw, budget):
    mapping, alias_sha = alias_mapping()
    cohorts = read_csv(cohort_raw, COHORT_FIELDS, LIMITS['cohort_rows'], budget)
    projects = read_csv(project_raw, PROJECT_FIELDS, LIMITS['project_rows'], budget)
    memberships = {}
    expected = {}
    for row in cohorts:
        c, e, y = identifier(row['cohort_id']), identifier(row['event_id']), year_number(row['year'])
        key = c, e, y
        if key in memberships:
            raise AuditError('duplicate cohort membership')
        n = row['expected_projects']
        if n and not re.fullmatch(r'0|[1-9][0-9]{0,6}', n):
            raise AuditError('expected_projects must be blank or an integer 0–9999999')
        n = int(n) if n else None
        if (e, y) in expected and expected[e, y] != n:
            raise AuditError('inconsistent expected_projects for an event/year')
        expected[e, y] = n
        memberships[key] = dict(cohort_id=c, event_id=e, year=y, expected_projects=n)
    if not memberships:
        raise AuditError('at least one cohort membership is required')
    if len({(c, y) for c, e, y in memberships}) > LIMITS['groups']:
        raise AuditError('cohort/year group limit exceeded')
    records = {}
    identity_urls, url_ids = {}, {}
    duplicates = 0
    technologies = set()
    for line, row in enumerate(projects, 2):
        budget.check()
        p, e, y = identifier(row['project_id']), identifier(row['event_id']), year_number(row['year'])
        if (e, y) not in expected:
            raise AuditError(f'project record {line}: event/year absent from cohorts')
        title, url = clean_text(row['title']), valid_url(row['source_url'])
        if (p in identity_urls and identity_urls[p] != url) or (url in url_ids and url_ids[url] != p):
            raise AuditError('ambiguous project identity: project_id and source_url must be one-to-one')
        identity_urls[p], url_ids[url] = url, p
        status = row['annotation_status']
        if status not in ('complete', 'partial', 'unknown'):
            raise AuditError('annotation_status must be complete, partial, or unknown')
        try:
            labels = json.loads(row['technologies'])
        except (ValueError, RecursionError) as exc:
            raise AuditError('technologies must be a JSON array of strings') from exc
        if not isinstance(labels, list) or len(labels) > LIMITS['labels_per_record']:
            raise AuditError('technologies must be a JSON array of at most 32 labels')
        keys = [label_key(label) for label in labels]
        if status == 'unknown' and labels:
            raise AuditError('unknown annotations must have an empty technology array')
        canonical = sorted({mapping['aliases'].get(k, k) for k in keys})
        technologies.update(canonical)
        if len(technologies) > LIMITS['technologies']:
            raise AuditError('distinct technology limit exceeded')
        record = dict(project_id=p, event_id=e, year=y, title=title, source_url=url,
                      original_labels=labels, technologies=canonical, annotation_status=status)
        key = p, e, y
        if key in records:
            previous = {k: v for k, v in records[key].items() if k != 'input_rows'}
            if previous != record:
                raise AuditError('conflicting duplicate project/event/year; reconcile explicitly')
            records[key]['input_rows'].append(line)
            duplicates += 1
        else:
            records[key] = dict(record, input_rows=[line])
    counts = Counter((e, y) for p, e, y in records)
    for event, n in expected.items():
        if n is not None and n < counts[event]:
            raise AuditError('expected_projects is smaller than observed event records')
    return (sorted(records.values(), key=lambda r: (r['year'], r['event_id'], r['project_id'])),
            sorted(memberships.values(), key=lambda r: (r['year'], r['cohort_id'], r['event_id'])),
            sorted(technologies), mapping, alias_sha, duplicates)


def summarize(records, technologies, budget):
    """Union mentions per stable project; complete only if every selected record is complete."""
    by_project = defaultdict(list)
    for r in records:
        by_project[r['project_id']].append(r)
    budget.check(len(records) + len(by_project) * max(1, len(technologies)))
    total = len(by_project)
    complete = 0
    unknown = 0
    mentions, complete_mentions, incomplete_mentions = Counter(), Counter(), Counter()
    for group in by_project.values():
        labels = set().union(*(set(r['technologies']) for r in group))
        is_complete = all(r['annotation_status'] == 'complete' for r in group)
        is_unknown = all(r['annotation_status'] == 'unknown' for r in group)
        complete += is_complete
        unknown += is_unknown
        mentions.update(labels)
        (complete_mentions if is_complete else incomplete_mentions).update(labels)
    stats = {}
    for tech in technologies:
        m = mentions[tech]
        stats[tech] = dict(mentions=m, proportion=m / total if total else None,
                          complete_mentions=complete_mentions[tech],
                          complete_proportion=complete_mentions[tech] / complete if complete else None,
                          possible_upper=(m + total - complete - incomplete_mentions[tech]) / total if total else None)
    return dict(projects=total, complete=complete, partial=total - complete - unknown,
                unknown=unknown, event_records=len(records), technologies=stats)


def analyze(project_raw, cohort_raw, budget=None):
    budget = budget or Budget()
    records, memberships, techs, mapping, alias_sha, duplicates = load(project_raw, cohort_raw, budget)
    events = defaultdict(list)
    for index, record in enumerate(records):
        record['record_id'] = index
        events[record['event_id'], record['year']].append(record)
    groups = []
    grouped = defaultdict(list)
    for member in memberships:
        grouped[member['cohort_id'], member['year']].append(member)
    for (cohort, year), members in sorted(grouped.items(), key=lambda p: (p[0][1], p[0][0])):
        selected = [r for m in members for r in events[m['event_id'], year]]
        composition = []
        for m in members:
            event_records = events[m['event_id'], year]
            n = m['expected_projects']
            composition.append(dict(event_id=m['event_id'], expected_projects=n,
                                    coverage=len(event_records) / n if n else None,
                                    summary=summarize(event_records, techs, budget)))
        summary = summarize(selected, techs, budget)
        groups.append(dict(group_id=len(groups), cohort_id=cohort, year=year,
                           summary=summary, events=composition,
                           record_ids=[r['record_id'] for r in selected],
                           cross_event_excess=len(selected) - summary['projects']))
    comparisons = []
    for i, before in enumerate(groups):
        for after in groups[i + 1:]:
            budget.check()
            common = sorted({e['event_id'] for e in before['events']} & {e['event_id'] for e in after['events']})
            b_records = [r for e in common for r in events[e, before['year']]]
            a_records = [r for e in common for r in events[e, after['year']]]
            b_sum, a_sum = summarize(b_records, techs, budget), summarize(a_records, techs, budget)
            usable = [e for e in common if events[e, before['year']] and events[e, after['year']]]
            bs = {e['event_id']: e['summary'] for e in before['events']}
            az = {e['event_id']: e['summary'] for e in after['events']}
            changes = {}
            for tech in techs:
                bp = before['summary']['technologies'][tech]['proportion']
                ap = after['summary']['technologies'][tech]['proportion']
                bcp, acp = b_sum['technologies'][tech]['proportion'], a_sum['technologies'][tech]['proportion']
                deltas = [az[e]['technologies'][tech]['proportion'] - bs[e]['technologies'][tech]['proportion'] for e in usable]
                delta = ap - bp if bp is not None and ap is not None else None
                changes[tech] = dict(delta=delta, common_delta=acp - bcp if bcp is not None and acp is not None else None,
                                     equal_event_delta=sum(deltas) / len(deltas) if deltas else None,
                                     reversal=bool(delta is not None and deltas and
                                                   ((delta < 0 and all(d > 0 for d in deltas)) or
                                                    (delta > 0 and all(d < 0 for d in deltas)))))
            before_ids, after_ids = set(before['record_ids']), set(after['record_ids'])
            budget.check(len(records) * 2 + len(techs) * len(usable))
            comparisons.append(dict(before=i, after=after['group_id'], common_events=common,
                                    nonempty_common_events=usable, before_common=b_sum, after_common=a_sum,
                                    overlapping_project_ids=sorted({r['project_id'] for r in records if r['record_id'] in before_ids} &
                                                                   {r['project_id'] for r in records if r['record_id'] in after_ids}),
                                    technologies=changes))
    result = dict(schema_version='1.0', notice=NOTICE, limits=LIMITS, normalization={**mapping, 'unicode_version': unicodedata.unidata_version},
                  provenance=dict(projects_sha256=digest(project_raw), cohorts_sha256=digest(cohort_raw), aliases_sha256=alias_sha),
                  diagnostics=dict(input_project_rows=len(records) + duplicates, duplicate_rows_collapsed=duplicates,
                                   unique_projects=len({r['project_id'] for r in records}), event_records=len(records)),
                  technologies=techs, memberships=memberships, records=records, groups=groups, comparisons=comparisons)
    budget.check()
    return result
