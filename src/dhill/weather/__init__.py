"""Weather providers: synthetic scenarios, Open-Meteo and CSV."""

from .base import Weather
from .csvio import load_weather_csv
from .openmeteo import WeatherUnavailable, fetch_archive, fetch_weather
from .synthetic import SCENARIOS, synthetic_weather

__all__ = [
    "SCENARIOS",
    "Weather",
    "WeatherUnavailable",
    "fetch_archive",
    "fetch_weather",
    "load_weather_csv",
    "synthetic_weather",
]
