# Five-minute demo (no slides)

The demo is graded on whether the system behaves, not on presentation skill. Rehearse it twice, with a timer.

| Time | Who | What to do and say |
| --- | --- | --- |
| 0:00 | Member 1 (product) | Repository already cloned. Run `python run.py`; the page opens. "One command, everything read from committed files." |
| 0:30 | Member 1 | Read the headline: Kazakhstan's latest rate, its quarter, the change on a year earlier, and the next-quarter forecast. |
| 1:00 | Member 2 (econometrics) | Pick Turkestan + Shymkent. Walk the driver panel: momentum, marriages, income, housing. Say the drivers are small and momentum dominates. |
| 1:45 | Member 2 | Move the marriage slider. The forecast and the 90% band move, and the decision signal updates. "The band comes from the covariance matrix in model/artifact.json." |
| 2:30 | Member 3 (data) | Turn off Wi-Fi and reload. Point at the "Offline … cached data" label. |
| 3:00 | Member 3 | Rename `model/artifact.json` and reload. Show the plain-language message. Rename it back. |
| 3:30 | Member 2 | Results: beats the benchmark on RMSE (ratio from note Section 3), but Diebold–Mariano is not significant at 5%, and on births counts the benchmark wins. |
| 4:15 | Member 1 | Decision rule: "If the 90% interval lies wholly below last year's quarter, the akimat plans for the forecast percentage fewer births; otherwise it plans at last year's level, because smaller moves are noise." |
| 5:00 | All | Questions. Anyone may be asked about any part; use the defence-prep section of the project doc. |

Have ready: the GitHub page, `outputs/technical_note.pdf` and `model/artifact.json` open in an editor.
