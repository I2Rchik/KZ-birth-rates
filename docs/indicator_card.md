# Indicator card (Section 1 of the technical note, verbatim)

| Element | Statement |
| --- | --- |
| Concept | How many babies are born per 1,000 residents of each region this quarter, and what next quarter is likely to bring. Regional authorities need it to plan maternity capacity, kindergartens and school places. |
| Formula | CBR(i,q) = 4 × 1,000 × B(i,q) / P̄(i,q). B = live births registered in the 3 months of quarter q in region i. P̄ = average resident population over the quarter (mean of the populations at the start of q and of q+1). The factor 4 annualises the rate. |
| Unit and scale | Live births per 1,000 population, annualised. Changes are shown year-on-year, in births per 1,000 and in percent. |
| Frequency and lag | Quarterly, built from monthly data. Published about 40–45 days after the period ends (the January–March 2025 release came out on 12 May 2025). |
| Coverage | 16 harmonised regions on pre-2018 borders (14 oblasts, Astana, Almaty city). 2010Q1 to the latest published quarter. |
| Source and vintage | Bureau of National Statistics, Taldau database: births, marriages, population by region. Identifiers and retrieval dates: see `data/raw/SOURCES.md`. Monthly data are revised when annual data are finalised. |
| Transformations | (1) Monthly → quarterly sums. (2) Border harmonisation: Abai → East Kazakhstan, Zhetisu → Almaty oblast, Ulytau → Karaganda (split 8 June 2022); Shymkent → Turkestan (2018). (3) Natural log. (4) Four-quarter difference to remove seasonality. No interpolation of births. Annual population stocks, if used, are interpolated linearly. |
| Known weaknesses | Counts births by registration date, not conception. Crude rate ignores age structure. Harmonised units hide the new regions. Migration into the three big cities moves the denominator. |
