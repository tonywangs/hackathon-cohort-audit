# Resource bounds and failure behavior

The runtime uses only Python's standard library. The installed CLI is currently
Linux-only because it uses `renameat2(RENAME_NOREPLACE)` for exclusive atomic
publication and POSIX signals for its wall-clock deadline. Reports can be opened
as local files in Chromium on other operating systems; only Linux Chromium was
exercised in this environment. Python 3.12 was tested; source syntax targets 3.10+.
No Windows/macOS CLI compatibility is claimed.

| Bound | Value |
| --- | --- |
| Bytes per CSV input | 4 MiB, read at most limit + 1 |
| Input project rows (including duplicates) | 5,000 |
| Cohort membership rows | 128 |
| Cohort/year groups | 16 |
| Distinct normalized technologies | 64 |
| Labels per project row | 32 |
| Original label length | 100 Unicode characters |
| Title/source URL length | 1,000 Unicode characters |
| CSV field length | 8,000 characters |
| Computation budget | 2,000,000 charged work units |
| Runtime | 30 elapsed seconds after CLI argument parsing; may be lowered |
| `report.json` | 8 MiB |
| `report.html` | 10 MiB |
| Mounted evidence rows | 25, with previous/next and full filtered JSON download |
| Trend rows | at most 64 |
| Event rows for the two selected groups | at most 256 (usually fewer) |

The computation budget charges record scans, distinct-project × technology cells
for summaries, comparison overlap scans, and technology × shared-event deltas.
It is a conservative application work counter, not an exact CPU instruction count.
Parsing and serialization are separately bounded by bytes and the runtime timer.
Not every simultaneous combination of individual maxima is accepted: the work or
report-size limit may reject it. There is no configurable unbounded mode.
The report keeps all accepted data in memory but mounts only a bounded evidence
page. Browser interactions scan at most 5,000 records, 64 technologies and 128
memberships; they do not materialize an unbounded DOM.

Both outputs are completely serialized and size-checked before writing. A hidden
staging directory is created beside the destination, files are flushed and fsynced,
and a `complete.json` manifest records artifact sizes and hashes. A single exclusive
rename publishes the finished bundle. Existing directories, files and dangling
symlinks are collisions, including a competing writer creating an empty directory
between validation and publication. Inputs are never output targets. The parent
output directory must already exist. Output is created with private temporary-directory
permissions; do not use report generation as a shared multi-user write service.

Validation, serialization, disk-write failures, SIGINT/SIGTERM and normal timeouts
return nonzero and remove staged files. Exit 0 means a full bundle was published;
2 means failure; 130 means cancellation. Publication is a commit point: a signal
arriving after the rename may leave a fully complete bundle. SIGKILL, machine loss,
or filesystem failure cannot run Python cleanup and may leave a hidden
`.cohort-audit-*` staging directory; it is not a published analysis. Parent-directory
fsync/crash durability across sudden power loss is not guaranteed. No partial output
is labeled complete. Verify `complete.json` hashes when transferring a bundle.

The tests cover malformed CSV/JSON, ambiguous identities, input and computation
limits, deterministic serialization, unchanged inputs, collision races, injected
serialization/fsync/publication failures, actual signal handlers, an external
SIGTERM during writing, and a sub-microsecond deadline. These are bounded tests,
not a proof against all OS/storage failure modes. Limits concern artifacts and
work, not a hard process RSS sandbox; measured peak RSS is in `results/benchmark.json`.
