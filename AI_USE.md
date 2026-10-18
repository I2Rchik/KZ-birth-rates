# AI-use declaration (annex)

Disclosed use carries no penalty under the brief. Undisclosed use is an integrity violation, so log every substantive use here.

| Date | Tool | Used for | What it produced | Prompt (summary) |
| --- | --- | --- | --- | --- |
| 2026-10-18 | Claude (Anthropic), Opus 5.5, in claude.ai | Code | First version of the whole repository: data layer, econometrics module, model layer, website, tests, synthetic test fixture | "Do it all yourself… build a model that predicts birth rates each quarter for each Kazakhstan region" |
| 2026-10-18 | Claude | Prose | Drafts of the registration page, indicator card, pre-registration memo, README and technical-note skeleton | same session |
| 2026-10-18 | Claude | Search | Candidate references, located with web search | same session |

## What we verified ourselves, and how

Fill this in before submission. Each line needs a name and a method.

- [ ] Every reference opened by a team member. The DOI resolves and the paper contains the claim we cite it for.
- [ ] Each formula in `src/econometrics.py` checked against its source paper (ADF, KPSS, Driscoll–Kraay, Pesaran CD, Diebold–Mariano).
- [ ] Results cross-checked against an independent package: run the main regression and ADF/KPSS in statsmodels or Stata and compare.
- [ ] Each raw file downloaded by a team member, and the retrieval date recorded.
- [ ] The headline value on screen compared by hand with the Bureau's own published total for one quarter.
- [ ] The "forecast ignores the future" test read and understood by every member.

No number in the note may come from the AI tool's text. All numbers come from `outputs/`, which the code generates.
