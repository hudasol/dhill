# Data sources and provenance

| Source | Use | Terms and caveats |
|---|---|---|
| Open-Meteo forecast and archive | Temperature, dew point, wind, shortwave radiation, precipitation | Non-commercial free tier with rate limits (HTTP 429 observed); modelled data; switch to a licensed feed or own station for production |
| Open-Meteo air-quality (CAMS) | PM10 and dust concentrations | Modelled, uncertain in the Gulf; PM10 forecast spread assumed 50% |
| Component datasheets | Cell resistance class, capacity, limits, die throttling | Cited in profile notes; vendor values apply to vendor conditions |
| Textbooks | Convection correlations, radiation, absorptance ranges | Standard engineering references |
| Moore et al. 2012 and PV soiling literature | Thermal-network structure for field robots; deposition velocity for PM10 | Applied to robot geometry by analogy |

Profiles tag each parameter: measured, datasheet, textbook, assumption or calibrated. Illustrative profiles are L0 and say so in their header.
