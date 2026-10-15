# Cohort Audit

Compare technology **mentions** across local hackathon project cohorts, with
source-linked evidence, explicit missingness, and event-composition diagnostics.
No accounts, API keys, network requests, inference services, or web server are needed.

The included synthetic example shows why denominators matter: Python mentions fall
from **74% to 36% overall**, even though both event series rise by **10 percentage
points**. The report exposes the changing sample weights and lets you inspect every
contributing project. It does not estimate population adoption or causal effects.

## Run locally

Requires Linux and Python 3.10+ (tested with 3.12), with no pip packages.
The output directory must not already exist; its parent must exist.

```sh
python3 -m cohort_audit \
  --projects examples/projects.csv \
  --cohorts examples/cohorts.csv \
  --out report-output
```

Open `report-output/report.html` directly in Chromium. Select before/after cohorts,
filter technology names, inspect event coverage and per-event rates, and activate
a technology name to jump to its evidence. The explorer pages through 25 records
at a time; choose **All records** to include missing labels. Download full or
filtered JSON using the report buttons. Source links open only when activated.

The output bundle contains deterministic `report.json`, a self-contained
`report.html`, and `complete.json` with output hashes. Input hashes, original labels,
logical CSV row numbers and the versioned alias map are embedded. No generation
time, absolute input paths or runtime measurements affect report bytes.

## Install offline

A standard-library installer builds a self-contained Python zip application into
a chosen prefix. It needs no package index, venv, pip, build backend or network.
It refuses to overwrite an existing executable.

```sh
python3 scripts/install.py --prefix /tmp/cohort-install
/tmp/cohort-install/bin/cohort-audit \
  --projects examples/projects.csv \
  --cohorts examples/cohorts.csv \
  --out /tmp/my-cohort-report
```

The installed file still requires Python 3.10+ and Linux; it can run from outside
the source checkout. Remove that executable to uninstall. Use a new output directory
for each run. `--max-seconds 5` lowers the default 30-second deadline.

## Supply your own data

See the [exact CSV contract](docs/input-contract.md) before importing data. Projects
need stable IDs, event-series IDs, year, title, HTTP(S) source URL, a JSON array of
technology labels, and `complete` / `partial` / `unknown` annotation status.
Cohorts list event/year memberships and optional expected project totals.

Conflicting identities or duplicates are errors. Exact duplicates collapse with
input row evidence. Cross-event projects count once per cohort/year and retain
all event appearances in the evidence. Missing labels never imply technology
non-use. Reports embed every supplied record, so share them only as appropriate
for the underlying data.

## Verify

The full suite needs Node.js, Playwright **1.58.2** and its cached Chromium.
These are development-only dependencies. Provision them once if not already cached
(no browser or package downloads occur in verification):

```sh
npm install --prefix /tmp/cohort-browser --cache /tmp/cohort-npm-cache playwright@1.58.2 --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH=/tmp/cohort-browser/browsers /tmp/cohort-browser/node_modules/.bin/playwright install chromium
```

Then one command runs the independent 300-seed oracle, error-path tests, isolated
installed CLI with socket access blocked, fixture regeneration, Chromium interaction
checks with external networking blocked, bounded workload measurements, repeated
artifact hashes, input-integrity checks and publication size checks:

```sh
python3 scripts/verify.py \
  --playwright-module /tmp/cohort-browser/node_modules/playwright \
  --browser-path /tmp/cohort-browser/browsers
```

Missing browser dependencies fail the full command; they are never silently skipped.
For just the standard-library tests: `python3 -m unittest discover -v`.
Add `--record` to the full verification command to refresh measured results and plain
`results/tests.log`. Measurement values vary with the host; report hashes should not
vary for identical code, input and Python/Unicode environment.

## Documentation and evidence

- [Formulas, comparison semantics and sampling limitations](docs/methods.md)
- [Input identity, duplicate handling and alias normalization](docs/input-contract.md)
- [Resource limits, atomic output and platform limitations](docs/limits.md)
- [Primary sources, existing implementations and public-data acquisition attempt](docs/prior-work.md)
- [Actual workload measurements](results/benchmark.json), [Chromium checks](results/browser.json), and [test output](results/tests.log)

Only clearly labeled synthetic data is included. The inspected public project
dataset lacks an explicit uniform redistribution license. Real Devpost exports,
provider compatibility and population conclusions remain unvalidated. No novelty
claim, public website, or automated scraper is part of this application.
