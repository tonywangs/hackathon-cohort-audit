# Formulas and interpretation

Let `P` be the set of distinct supplied project IDs in a cohort/year, `N = |P|`.
For each project, union its labels over selected event appearances. Let `C` be the
subset whose selected appearances are all annotated complete, `Nc = |C|`.
For technology `t`, `M` is the number of projects mentioning `t`, `Mc` is the number
in `C` mentioning it, and `Mi` is the number outside `C` mentioning it.

| Output | Formula |
| --- | --- |
| Observed mention proportion | `M / N` |
| Complete-only mention proportion | `Mc / Nc` |
| Possible interval for fully captured label mentions | `[M / N, (M + (N - Nc) - Mi) / N]` |
| Aggregate change | `p_after - p_before` (HTML multiplies by 100 for percentage points) |
| Event coverage | observed distinct project/event records / supplied expected count |
| Event composition share | event records / all selected event records |

Undefined divisions are JSON `null` and displayed as unavailable, never zero.
The interval is an identification bound for **these supplied projects** assuming
captured positive labels are valid and complete lists exhaustive. It is not a
confidence interval or a bound on real technology use or unsampled projects.
Complete-only estimates can be selection biased. Partial records with positive
labels contribute to observed mentions, while incomplete records lacking that
label remain unresolved. Unknown records remain visible in every denominator.

## Comparisons

The JSON contains all unordered pairs of cohort/year groups, sorted by year then
cohort ID. Their `before`/`after` fields refer to group indices. The interface can
select either direction and reverses the signs. A same-group selection is explicitly
labeled; empty denominators stay unavailable.

A common event is an equal `event_id` present in both membership lists. Common-event
pooled proportions restrict each side to these occurrences and again deduplicate
project IDs across events. Each side's denominators and annotation counts are
included. The common event list can include empty occurrences: the pooled comparison
may consequently reflect which events have records on each side.

Equal-event change takes the mean of each event's observed proportion difference
over shared events **with at least one supplied project on both sides**. This
holds event weights equal, not project weights. It is a descriptive estimand:
small events receive the same weight as large ones; cross-event projects can
contribute in multiple event strata. If no event qualifies, the result is null.
The report lists excluded/nonempty shared series and event-level rates so this
choice is inspectable. It does not balance annotation completeness, sponsors,
project attributes, or participant composition within a series.

The composition-reversal flag requires a nonzero aggregate difference and at least
one nonempty common event, with **every** such event having a strictly opposite
nonzero difference. It is a diagnostic, not a causal conclusion. No flag does not
establish comparability. JSON also lists overlapping project IDs across sides;
comparisons involving the same projects are not independent samples.

## Synthetic demonstration

`examples/` contains only original synthetic data, with a deterministic generator,
SHA-256 provenance and CC0 dedication for the CSV fixtures. There is no random seed
for this fixed construction; the independent oracle suite uses seeds 0–299.

| Series | 2024 Python mentions | 2025 Python mentions | Change |
| --- | --- | --- | --- |
| high | 72/90 = 80% | 9/10 = 90% | +10 pp |
| low | 2/10 = 20% | 27/90 = 30% | +10 pp |
| pooled | 74/100 = 74% | 36/100 = 36% | −38 pp |
| equal event weight | 50% | 60% | +10 pp |

Both series improve, while the high-mention series loses sample weight. Restricting
to common events alone cannot fix this example: both series are already common.
The second synthetic cohort includes duplicate input rows, a cross-event project,
partial/unknown annotations, canonical Unicode equivalents, an unknown label, and
literal hostile-looking HTML. A third cohort is empty.

## Limits of inference

No random sampling design, population frame, or independent annotation audit is
available. Missingness may depend on technology, year, event, winners, or export
settings. Event series identifiers are importer judgments. Time comparisons may
reflect changes in organizers, disclosure conventions, annotation rules or project
resubmission. Self-reported labels can be inaccurate. No significance tests,
causal effects, population forecasts, or confidence intervals are justified here.
See [prior work and data access](prior-work.md) for the public-data dependency.
