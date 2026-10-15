# Prior work and data access

Reviewed 2026-10-15. This is a small offline audit implementation, not a claim of
novel statistical methodology or a validated Devpost adapter.

## Primary sources

- [Devpost: Metrics and reports](https://help.devpost.com/article/96-metrics-and-reports)
  documents organizer access to CSV exports and an option to exclude personally
  identifiable information. Export options, drafts, custom fields and access rights
  affect what is supplied. This tool accepts its own conservative CSV contract;
  it has not been tested against an actual organizer export or authenticated API.
- [Devpost terms of service](https://info.devpost.com/legal/terms-of-service)
  include restrictions on automated scraping. No Devpost scraper, credential flow,
  endpoint discovery, or source-URL fetch is implemented here. An authorized local
  export still needs a documented selection/annotation protocol and redistribution
  permission before it can become a shared fixture.
- E. H. Simpson, [The Interpretation of Interaction in Contingency Tables (1951)](https://doi.org/10.1111/j.2517-6161.1951.tb00088.x),
  provides the classic aggregation warning. We reviewed the publisher's summary,
  not the paywalled full article. The synthetic construction is original and does
  not reproduce the paper's data.
- Kristina Lerman, [Computational Social Scientist Beware: Simpson's Paradox in Behavioral Data (2017)](https://arxiv.org/abs/1710.08615v1),
  discusses how heterogeneous subgroups can make aggregate behavioral relationships
  misleading. Its abstract motivates displaying strata and their changing weights;
  no claim is made to reproduce the paper's experiments or proposed detector.

## Existing implementation inspected

[Global-Hackathon-EDA](https://github.com/alokgorithm/Global-Hackathon-EDA) analyzes
hackathon events across platforms. Its `Hackathon_Analysis.ipynb` was downloaded
and its code cells inspected: date cleaning, year/platform counts, subgroup plots,
and prize/participation comparisons. Those are event-level analyses rather than
project-level technology annotations. Our implementation uses no copied code or data.
The repository describes restricted educational licensing; it is not a source of
redistributable fixtures here. Reviewed notebook SHA-256:
`8d124c90dea2be8fc0f1490c365b5c593924ed3252e37c94291566f0859e31c2`.
The upstream `main` URL may change; this hash identifies the bytes inspected.

## Attempt to acquire a redistributable project dataset

We inspected the public card and fetched revision metadata for
[twangodev/devpost-hacks](https://huggingface.co/datasets/twangodev/devpost-hacks).
The card describes 2,222 projects with `built_with` labels and linked repository
README content. Revision inspected:
`3cb29f15841c7b61fd78a20ff12127e0846dc227`.
Its license metadata is `other`; the card gives a fair-use/research-use rationale
for Devpost content and says linked READMEs retain individual repository licenses.
This does not provide the explicit uniform redistribution permission required for
our sample. Acquisition therefore stopped at the card/metadata license check;
no dataset rows or README payloads were acquired or redistributed.

The [pinned dataset card](https://huggingface.co/datasets/twangodev/devpost-hacks/blob/3cb29f15841c7b61fd78a20ff12127e0846dc227/README.md)
had SHA-256 `61a6fa274879729bc3d3a7abfaaaa55f20f3393289051a84a8f30572d34c976e`.
The retrieved API metadata had SHA-256
`4a0443381ffd37ab269e3c919865d739561a809103cbf1b43dd46aca7663acf6`.
These are fingerprints of inspected documents, not a license grant or hashes of
an acquired data sample. Only original synthetic fixtures are shipped.

A real-data validation remains dependent on an authorized, explicitly redistributable
project sample with stable identities, cohort selection details and annotation
completeness. Its future provenance should include upstream revision, exact file
hashes, license/attribution, export options, selected events and exclusions, and a
manual audit of field mapping. Public visibility alone is not that permission.
