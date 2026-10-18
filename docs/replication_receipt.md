# Replication receipt (Week 6 peer session)

To be completed by the **reviewing team**, on their own machine, with no help from us (brief, Sections 11 and 18).

- Repository: https://github.com/I2Rchik/KZ-birth-rates (commit hash: __________)
- Reviewing team: ______________________________
- Machine and operating system: ______________________________
- Date: ____________

| # | Check (in this order) | Pass / Fail | Note |
| --- | --- | --- | --- |
| 1 | Clone and follow the README; the environment installs with no manual fixes | | |
| 2 | `python run.py` serves the site within 10 minutes of cloning | | |
| 3 | The landing view shows headline value, unit, reference quarter and latest change without scrolling | | |
| 4 | The page renders in under 3 seconds | | |
| 5 | Three driver contributions in `model/artifact.json` (`forecast → <region> → contributions`) match the screen | | |
| 6 | The scenario slider changes the output, and the 90% band changes with it | | |
| 7 | With the network off, reloading shows the data labelled as cached | | |
| 8 | With `model/artifact.json` renamed, reloading reports a missing model in plain language | | |
| 9 | The headline figure does not appear as a literal in `src/app.py`, `src/static/` | | |
| 10 | No credentials, tokens or personal data in the repository or its history (`git log -p --all \| grep -inE "password\|token\|secret\|api.?key"`) | | |

**Headline reproduction.** Run `python run.py check`.

- Kazakhstan forecast in the committed artifact: ______
- Value after the rebuild: ______
- Within ±0.01 births per 1,000? Yes / No

Signed (reviewing team members):

______________________ ______________________ ______________________
