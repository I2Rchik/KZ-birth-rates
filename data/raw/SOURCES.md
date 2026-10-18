# Sources

Every file here is an untouched download from Taldau, the statistical database of the Bureau of National Statistics, Agency for Strategic Planning and Reforms of the Republic of Kazakhstan (https://taldau.stat.gov.kz/ru). `manifest.json` holds each file's SHA-256 checksum, and `python run.py ingest` refuses to run if a file changes.

Only the file names were changed when the files were registered. Taldau names every download `data.csv` or `download.xls`. The `.csv.gz` files are gzip-compressed, tab-separated tables, which is exactly how Taldau serves them.

All files were retrieved on 18 October 2026. Two files come from Taldau's English interface, with region names transliterated from Kazakh (SHYGYS = East, SOLTUSTIK = North, BATYS = West); `src/regions.py` maps them. Each Taldau page has its own address; paste it into the "Page URL" lines below.

| File | Indicator in Taldau | Breakdown used | Frequency | Coverage |
| --- | --- | --- | --- | --- |
| births_quarterly_cumulative.csv.gz | Число родившихся (живыми), человек | regions, "Всего" | Cumulative January–quarter end | 2014Q1–2026Q2 (January–June 2022 absent in the source) |
| population_monthly.csv.gz | Численность населения на начало периода, человек | regions, "Всего" | Start of month | January 2011 – January 2024 |
| marriages_quarterly_cumulative.csv.gz | Number of registered marriages (Число зарегистрированных браков), English export | regions, "Total" | Cumulative January–quarter end | 2014Q1–2026Q2 (January–June 2022 absent) |
| income_per_capita_quarterly.csv.gz | Average per capita nominal monetary income of the population, tenge, English export | regions | Quarterly | 2010Q1–2026Q2 |
| marriages_annual.csv.gz | Число зарегистрированных браков, человек (КСП 612401) | regions, "Всего" | Annual | 2000–2025 (fallback only; not used while the quarterly file is present) |
| income_per_capita_annual.csv.gz | Среднедушевые номинальные денежные доходы населения, тенге | regions | Annual | 2000–2025 (fallback only) |
| housing_per_resident_annual.csv.gz | Обеспеченность жильем на одного проживающего, м² | regions, "Всего" | Annual | 2001–2025 |
| cpi_quarterly_by_region.xls | Индекс потребительских цен, товары и услуги (ГНКИПЦ01_2753), отчетный период к предыдущему периоду | regions | Quarterly | 2011Q1–2026Q3 |

## Rules applied in code (src/ingest.py, src/regions.py)

- **Regions only.** Taldau files also list districts (…РАЙОН), towns (Г.АКТОБЕ, АКСУ Г.А.), villages (С.АБАЙ), Alatau city administration (Г.А.АЛАТАУ) and the national total. All of these are dropped. Check: in every quarter, the 16 harmonised regions add up exactly to the national births total.
- **South Kazakhstan before 2018.** The population file lists Shymkent both inside South Kazakhstan and as a town, 2017–May 2018. Where the old-border region exists for a period, only it is used.
- **2022 regions.** Abai, Zhetisu and Ulytau are added to East Kazakhstan, Almaty oblast and Karaganda from the first period each is reported.
- **Population projection.** After January 2024, population is projected at each region's average monthly growth from January 2023 to January 2024. Every quarter that uses a projection is flagged.

## Downloaded but not used

- National employment, monthly (data.csv_4) and quarterly (second batch, data.csv): no regional breakdown.
- Per-capita income, monthly (second batch, data.csv_1): national total only.
- Duplicate downloads: data.csv_6 is identical to data.csv_5, and download_1.xls is identical to download.xls.
- Marriages in the old binary .xls format (2026.10.18-17.10.39.xls): the same annual figures as marriages_annual.csv.gz.

## Page URLs (fill in)

- births:
- population:
- marriages (quarterly):
- marriages (annual):
- income (quarterly):
- income (annual):
- housing_pc:
- cpi:
