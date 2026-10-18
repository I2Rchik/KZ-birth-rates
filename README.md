# Kazakhstan regional birth rate: now and next quarter

A local website that shows the quarterly crude birth rate (live births per 1,000 population, annualised) for 16 harmonised regions of Kazakhstan. It also shows a one-quarter-ahead forecast from a pre-registered panel ARDL model, what drives that forecast, and a scenario control.

ECO1209 Data Analysis & Economic Forecasting (KBTU), group assignment "Build an Indicator".

## Install (clean machine, under 10 minutes)

Requires Python 3.11 or newer.

```bash
git clone <this repository> kz-births
cd kz-births
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

This opens http://127.0.0.1:8050. The site reads only committed files (`data/processed/` and `model/artifact.json`), so it works offline. Without a network connection it says the data are a cached snapshot. Stop it with Ctrl+C.

## Refresh the data

1. Download each series listed in `data/raw/SOURCES.md` from stat.gov.kz (Taldau). Export it by region, monthly or quarterly, as .xlsx.
2. Register each download. This copies the file into `data/raw/` and records its checksum and retrieval date:

   ```bash
   python run.py register-raw ~/Downloads/births.xlsx --series births \
       --url "https://taldau.stat.gov.kz/..." --id "<indicator id shown in Taldau>" \
       --navigation "Taldau > Demography > ... > by region, monthly"
   ```

3. Copy the same details into `data/raw/SOURCES.md`.

Raw files are written once and never edited. The data layer refuses to run if a raw file's checksum has changed.

## Re-estimate

```bash
python run.py rebuild   # data/raw -> data/processed -> model/artifact.json + outputs/
python run.py check     # rebuild and confirm every headline reproduces within ±0.01 per 1,000
python run.py test      # automated tests, including "the forecast ignores the future"
```

Delete `data/processed/` and run `python run.py ingest`, and the folder is restored byte for byte.

## Architecture

| Layer | Entry point | Reads | Writes |
| --- | --- | --- | --- |
| Data | `src/ingest.py` | `data/raw/` + `manifest.json` | `data/processed/panel.csv`, `meta.json` |
| Model | `src/model.py` (+ `src/econometrics.py`) | `data/processed/` | `model/artifact.json`, `outputs/` |
| Presentation | `src/app.py` + `src/static/` | `data/processed/`, `model/artifact.json` | nothing |

The app contains no regression and estimates nothing. It re-reads the artifact on every request. The scenario control applies the stored coefficients and covariance matrix to the slider value.

## Error states

| Situation | What the page says |
| --- | --- |
| No network | Chip: "Offline: stat.gov.kz unreachable. Showing cached data retrieved <date>" |
| `model/artifact.json` missing or renamed | "The model is missing: model/artifact.json was not found…" |
| `data/processed/` missing | "Processed data not found… Rebuild it with: python run.py rebuild" |
| A region lacks an input for the forecast quarter | "No forecast for <region>: missing <series> for <quarter>" |
| Raw file edited after download | `rebuild` stops: "data/raw/<file> changed since it was downloaded" |

## Known limitations

- Crude rate, not fertility per woman. Age structure differences between regions are not removed.
- Units use borders from before 2018: Abai, Zhetisu, Ulytau and Shymkent are added to their parent regions.
- The latest 4 quarters are operational data that the Bureau later revises.
- Uncertainty bands assume normal errors. The residuals fail normality, so treat the 90% band as approximate.
- Driver relationships are conditional correlations, not causal effects. There is no identification strategy.

## Security check (acceptance test 10)

```bash
git log -p --all | grep -inE "api[_-]?key|secret|password|token\s*[:=]|PRIVATE KEY" || echo "nothing found"
```

No paid APIs, credentials or personal data are used. The data are public aggregates by region.

## Borrowed code

None. The statistical tests in `src/econometrics.py` are written from the formulas in the cited papers and use numpy/scipy only. The test fixture in `tests/fixtures/` is synthetic and is never used as data.

## Reproducibility

- Monte Carlo p-values use seed 20261018 (`src/config.json`).
- Library versions are pinned in `requirements.txt`. Tested on Python 3.13.
- Replication tolerance: every regional and national forecast within ±0.01 births per 1,000 (`python run.py check`).
