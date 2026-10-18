# Sources

Every file in this folder is an untouched download. `manifest.json` records each file's SHA-256 checksum, and `python run.py ingest` refuses to run if a file has changed. Fill one block per file when you register it. Leave nothing blank: the series identifier and the navigation path are what make the data traceable.

Publisher for all series: Bureau of National Statistics, Agency for Strategic Planning and Reforms of the Republic of Kazakhstan. Statistical database "Taldau": https://taldau.stat.gov.kz

Required for the model: births, marriages, population. The pre-registered drivers also need wage, cpi, unemployment and housing. If one of these is missing, `model.py` drops that driver and lists the drop as a deviation.

| Series key | What to download | Breakdown | Frequency | Years |
| --- | --- | --- | --- | --- |
| births | Number of live births (Число родившихся) | all regions, incl. Abai, Zhetisu, Ulytau, Shymkent | monthly | 2010 – latest |
| marriages | Number of registered marriages (Число зарегистрированных браков) | all regions | monthly | 2010 – latest |
| population | Population at the start of the month, or at 1 January (Численность населения) | all regions | monthly or annual | 2010 – latest |
| wage | Average nominal monthly wage (Среднемесячная номинальная заработная плата) | all regions | quarterly | 2010 – latest |
| cpi | Consumer price index, previous month = 100 (ИПЦ к предыдущему месяцу) | all regions | monthly | 2010 – latest |
| unemployment | Unemployment rate (Уровень безработицы) | all regions | quarterly | 2010 – latest |
| housing | Residential floor space commissioned, m² (Ввод в эксплуатацию жилых зданий) | all regions | monthly | 2010 – latest |

If the CPI you download uses another base (for example, the same month last year = 100), set `"base"` in `src/config.json` and record that here.

---

## births

- File: `births_monthly.xlsx`
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:
- Revised? Yes. Monthly operational data are replaced by final annual data.

## marriages

- File:
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:

## population

- File:
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:
- Timing: start of month / 1 January (delete one)

## wage

- File:
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:

## cpi

- File:
- Base: previous month = 100
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:

## unemployment

- File:
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:

## housing

- File:
- URL / API query:
- Series identifier:
- Navigation path:
- Retrieval date:
