# Input contract (schema 1.0)

Use UTF-8 CSV (optional BOM), comma delimiters and standard double-quote escaping.
Headers must match exactly and in order. Blank lines, extra columns, invalid UTF-8,
malformed quoting, and unsupported field values fail the whole analysis. Inputs are
read-only. Nothing is fetched, evaluated, interpolated into commands, or inferred
from project prose. Avoid personal information in titles and URLs: the report embeds
all supplied records, including evidence outside the current selection.

## projects.csv

```csv
project_id,event_id,year,title,source_url,technologies,annotation_status
sample-1,series-a,2025,SYNTHETIC example,https://example.invalid/sample-1,"[""Python"",""python3""]",complete
sample-2,series-a,2025,SYNTHETIC unannotated,https://example.invalid/sample-2,[],unknown
```

| Field | Meaning and validation |
| --- | --- |
| `project_id` | Global stable identity, preserved across event appearances and years. 1–80 ASCII letters/digits plus `_.:-`, starting with a letter/digit. |
| `event_id` | Stable **event series/stratum** ID, same across years only when comparison is meaningful. An occurrence is `(event_id, year)`. At most one occurrence per series/year; separate multiple editions explicitly. Same identifier rules as projects. |
| `year` | Four digits, 1000–2999. An explicit reporting year; never inferred from URL or title. |
| `title` | Nonblank text, at most 1,000 characters. Rendered literally. |
| `source_url` | Absolute HTTP(S), at most 1,000 characters, no credentials, whitespace, controls, backslash, `<`, `>`, or double quote. Stored exactly; not fetched or validated against a provider. |
| `technologies` | JSON array of 0–32 nonblank string labels, each at most 100 characters. Original spelling, order and repetition are preserved. |
| `annotation_status` | Exactly `complete`, `partial`, or `unknown`, as attested by the importer. |

Identifiers are case-sensitive and never trimmed. Text and labels cannot contain
Unicode control (`Cc`) or surrogate (`Cs`) characters. Unicode formatting characters
are preserved; labels and titles can contain non-ASCII scripts. Whitespace surrounding
labels is retained in evidence and stripped only for matching.

`complete` means the supplied label list was exhaustively captured under the importer's
annotation protocol. `complete` with `[]` is a known empty list. `partial` permits
known positive labels but does not establish absence of any other labels; an empty
partial list is allowed. `unknown` requires `[]`. These statuses describe label
collection, **not validation of actual technology use**. Never automatically mark a
blank provider field complete without establishing what it means.

### Identity and duplication

Each project ID has exactly one literal source URL, and each literal URL exactly one
project ID, across the entire input. Conflicts fail. No URL canonicalization is
attempted: redirects, fragments, tracking parameters and provider ID migrations
must be reconciled upstream. IDs must not be invented from titles. These checks
cannot prove two distinct supplied IDs represent distinct real projects.

The key for a record is `(project_id, event_id, year)`. Exact parsed duplicates
collapse; their 1-based logical CSV record numbers (header = 1) remain in `input_rows`.
Any difference in title, URL, annotation status or the original label array is a
conflict, even when aliases would make the arrays equivalent. Reconcile it explicitly;
there is no last-row-wins rule. CSV quoting or JSON array whitespace alone does not
change parsed equality. A project appearing in different events/years may have
different titles or labels but must retain the same URL.

Within each cohort/year, a project counts once. Mentions are the union across its
selected event records. Its annotation is complete only if every selected record
is complete, unknown only if every record is unknown, and partial otherwise. Evidence
retains each event appearance. Event-level totals therefore need not sum to the
cohort's distinct-project count. `cross_event_excess` exposes that difference.

## cohorts.csv

```csv
cohort_id,event_id,year,expected_projects
sample,series-a,2025,10
sample,series-b,2025,
empty-example,empty-series,2025,0
```

A row includes one event occurrence in a named cohort/year; cohort IDs follow the
same identifier rules. Empty observed cohorts are represented by memberships with
no matching project rows. At least one membership is required. Multiple cohorts may
include the same event, but duplicate `(cohort_id, event_id, year)` rows fail.
Every project occurrence must appear in at least one membership; unmatched records
are rejected rather than silently dropped.

`expected_projects` is blank (unknown) or an integer 0–9,999,999 without leading
zeros. It is an optional independently supplied count of project/event submissions,
not participants. It must agree across all memberships of an occurrence, including
blank versus nonblank, and cannot be less than observed distinct event projects.
A coverage fraction is shown only for a positive expected count; zero/zero is
undefined. An expected count does not validate representativeness or provide the
missing projects' labels. Cohorts with overlapping projects cannot obtain a unique
population denominator by simply summing expected event counts.

## Normalization

Mapping version `2026-10-15.1` is stored in `cohort_audit/aliases.json` and embedded
with its file hash. For each original label: NFC → strip surrounding whitespace →
Unicode casefold → explicit alias lookup. Python's Unicode database version is
recorded in the report. Unknown normalized keys remain distinct technologies.
No fuzzy matching, category guessing, stemming, prose extraction, provider lookup,
or inference of an “AI” category occurs. `react native` is not `react`; `java` is
not `javascript`. Each canonical label counts at most once per project.

Updating aliases requires editing the explicit mapping, bumping its version,
reviewing equivalences, and rerunning verification. There is no imported executable
alias plugin. Results remain reproducible only with the same inputs, mapping,
application files and compatible Python/Unicode environment.
