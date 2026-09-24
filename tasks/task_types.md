# Task types — standalone task layer v1

Eleven repeatable units of work. One owner, one deliverable, one speed class each.
Weeks to result: decision 2 · weeks 6 · months 12 · cycles 24 · continuous = standing program.

| # | type | deliverable | owner | weeks | lane |
|---|---|---|---|---|---|
| T2 | Expand an existing owned page | An existing brand page is extended into a full answer for one patient intent, to the citability spec. | Digital + Medical | 6 | A |
| T3 | Citability rewrite of a losing page | A page of ours that is already cited but loses the answer is audited and rewritten against the pages that win it. | Digital + Medical | 6 | A |
| T4 | Publish a new owned evidence page | A new MLR-compatible citable page for an intent we own nothing on. | Digital + Medical | 6 | A |
| T5 | Listings, directory & reference-web data | Our brand data is correct and present in the directories, drug-listing services and reference sites these answers cite. | Digital + Medical | 12 | A |
| T6 | Third-party placement (commercial & editorial) | The brand enters the commercial and editorial pages that actually answer the question. | Digital + PR | 12 | A |
| T10 | Hostile source response | One litigation-linked domain is handled end to end: legal decision first, then PR displacement with authoritative content. | Legal + PR | 12 | A |
| T7 | Label-clarity content | Content carrying the exact prescribing-information citation the models misread. | Medical + Digital | 6 | B |
| T8 | Medical/Regulatory escalation & off-label dossier | A dossier of affected questions plus the regulatory decision on whether content may be built. | Medical / Regulatory | 6 | B |
| T9 | Provider error reports | Structured error reports filed with the model vendors, citing the prescribing information. | Citere + Medical | 6 | B |
| T12 | Executive decision (commercial / channel floor) | A decision, not content: accept the channel floor or fix the commercial program. | Commercial / CMO | 2 | C |
| T1 | Monitor & verify position | Standing monitoring of the sources feeding a held position, with drift alerts. | Citere | program | P |

`T10 Hostile source response` runs two tracks in order: **legal decision** (cease-and-desist / public
statement / ignore) and then **PR displacement** with authoritative content and earned coverage.

## Causes and evidence per type

| # | cause codes it answers | evidence available in the data |
|---|---|---|
| T2 | COMP-CONTENT, SOURCE-PREF, SOURCE-LEAK, UNCLAIMED | our page URL from inventory, cited domains, SERP rank, sample answers, $ and demand |
| T3 | SYNTH | our cited domain, the winning domains, SERP rank, sample answers, $ and demand |
| T4 | SOURCE-LEAK, SOURCE-PREF, COMP-CONTENT, UNCLAIMED | subtopic, cited domains, SERP gap, inventory verdict (none/partial), $ and demand |
| T5 | SOURCE-PREF, INSTITUTIONAL, NOT-CHOSEN, KNOW | the exact directory domains cited, SERP occupiers, $ and demand |
| T6 | COMP-CONTENT, COMMERCIAL-GAP, NOT-CHOSEN | the commercial domains cited, competitor split, $ and demand |
| T10 | HOSTILE | the litigation domains cited, affected questions, sample answers, $ and demand |
| T7 | LABEL-GAP | subtopic and the label section; no cited domains (R4/R5 answers rarely cite) — evidence is the answer text |
| T8 | COMP-OFFLABEL, LABEL-GAP | subtopic, affected questions, sample answers; cited domains present on only 8% of points |
| T9 | LABEL-GAP | subtopic, sample answers, the PI citation; no cited domains |
| T12 | INSTITUTIONAL, SYNTH, COMP-CONTENT, SOURCE-PREF | cited institutional domains, channel split, $ and demand — shown to justify NOT spending |
| T1 | WORKING, SOURCE-LEAK | the source set feeding the held answer, drift baseline |
