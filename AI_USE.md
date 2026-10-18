# AI-use declaration (annex)

Disclosed use carries no penalty under the brief; undisclosed use is an integrity violation.

| Date | Tool | Used for | What it produced | Prompt (summary) |
| --- | --- | --- | --- | --- |
| 2026-10-18 | Claude (Anthropic), Opus 5.5, claude.ai | Code | The whole repository: data layer, econometrics module, model layer, website, tests, synthetic fixture, GitHub Pages export | "Do it all yourself… build a model that predicts birth rates each quarter for each Kazakhstan region"; later "do everything you can" |
| 2026-10-18 | Claude | Prose | Registration page, indicator card, pre-registration memo, README, SOURCES.md, technical note wording, demo script | Same session |
| 2026-10-18 | Claude | Analysis | Choice of harmonisation rules, diagnosis of double counting in the Taldau files, interpretation of results | Same session |
| 2026-10-18 | Claude | Search | References (web search). Each was opened by the tool and its details checked against the source page | Same session |

The team downloaded the data from Taldau on 2026-10-18.

## Process facts we disclose

- The pre-registration memo was written on 18 October 2026, before any data were loaded. The model was estimated later the same day. The memo was **not** time-stamped by the course system before estimation.
- Every deviation from the memo is listed in Section 3 of the technical note, and is generated from `src/config.json` and the model run.

## Verification record

Already done in the repository:

- Coefficients re-estimated an independent way (an explicit dummy for each region instead of the within transformation): identical to 8 decimals. This is `tests/test_pipeline.py::RealDataCrossCheck`, which runs with `python run.py test`.
- Region totals: the 16 harmonised regions sum exactly to Taldau's national births total in every quarter.
- `python run.py check`: the headline forecasts reproduce within ±0.01 births per 1,000.

Still to do by the team (write a name and the date next to each):

- [ ] Run `python tests/crosscheck_packages.py` (linearmodels and statsmodels) and paste the output below. Done by: ______
- [ ] Open every reference link in the note's Annex D and confirm the paper says what we cite it for. Done by: ______
- [ ] Compare one quarter's national births on screen with the Bureau's own release. Done by: ______
- [ ] Each member has read and can explain `src/ingest.py`, `src/model.py`, `src/econometrics.py` and `src/app.py`. Signed: ______

Cross-check output:

```
(paste here)
```
