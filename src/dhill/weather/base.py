"""Weather container and conversion to solver forcing."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..physics import solar
from ..physics.constants import c_to_k, pressure_at_elevation
from ..physics.thermal import Forcing

HOUR_S = 3600.0


def _as_times(times) -> np.ndarray:
    return np.asarray(times).astype("datetime64[s]")


@dataclass
class Weather:
    """Hourly (or finer) weather for one site, in UTC.

    ``ghi_wm2`` is optional. When given, it scales the clear-sky beam and diffuse
    components so cloud and dust attenuation in the forecast are respected.
    """

    times_utc: np.ndarray
    t_air_c: np.ndarray
    dew_c: np.ndarray
    wind10_ms: np.ndarray
    pm10_ugm3: np.ndarray
    precip_mm_h: np.ndarray
    lat: float
    lon: float
    altitude_m: float = 0.0
    ghi_wm2: np.ndarray | None = None
    source: str = "unknown"
    label: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.times_utc = _as_times(self.times_utc)
        n = self.times_utc.shape[0]
        for name in ("t_air_c", "dew_c", "wind10_ms", "pm10_ugm3", "precip_mm_h"):
            arr = np.asarray(getattr(self, name), dtype=float)
            if arr.shape != (n,):
                raise ValueError(f"{name} must have shape ({n},), got {arr.shape}")
            setattr(self, name, arr)
        if self.ghi_wm2 is not None:
            self.ghi_wm2 = np.asarray(self.ghi_wm2, dtype=float)
            if self.ghi_wm2.shape != (n,):
                raise ValueError("ghi_wm2 shape mismatch")
        if n < 2:
            raise ValueError("need at least two time samples")
        steps = np.diff(self.times_utc).astype("timedelta64[s]").astype(float)
        if np.any(steps <= 0):
            raise ValueError("times must be strictly increasing")

    @property
    def n(self) -> int:
        return int(self.times_utc.shape[0])

    @property
    def span_hours(self) -> float:
        return float(
            (self.times_utc[-1] - self.times_utc[0]).astype("timedelta64[s]").astype(float) / HOUR_S
        )

    def _grid(self, dt_s: float) -> np.ndarray:
        t0 = self.times_utc[0]
        total = (self.times_utc[-1] - t0).astype("timedelta64[s]").astype(float)
        return np.arange(0.0, total + 1e-6, dt_s)

    def to_forcing(self, dt_s: float = 600.0) -> Forcing:
        """Interpolate to a uniform grid and add the solar geometry."""
        t0 = self.times_utc[0]
        x = (self.times_utc - t0).astype("timedelta64[s]").astype(float)
        grid = self._grid(dt_s)

        def lin(y):
            return np.interp(grid, x, np.asarray(y, dtype=float))

        times = t0 + grid.astype("timedelta64[s]")
        elev, _ = solar.solar_position(times, self.lat, self.lon)
        dni_c, dhi_c, ghi_c = solar.clear_sky(elev, self.altitude_m)
        if self.ghi_wm2 is not None:
            ghi_obs = lin(self.ghi_wm2)
            k = np.where(ghi_c > 20.0, np.clip(ghi_obs / np.maximum(ghi_c, 1.0), 0.0, 1.15), 0.0)
            # clouds and dust cut the beam more than the diffuse sky
            dni = dni_c * np.clip(k**1.5, 0.0, 1.15)
            ghi = ghi_obs * (ghi_c > 20.0)
            dhi = np.clip(ghi - dni * np.sin(np.maximum(elev, 0.0)), 0.0, None)
        else:
            dni, dhi, ghi = dni_c, dhi_c, ghi_c
        sin_e = np.sin(np.maximum(elev, 0.0))
        cos_e = np.cos(np.maximum(elev, 0.0))
        hours_local = np.asarray(solar.mean_solar_hour(times, self.lon), dtype=float)
        rain = lin(self.precip_mm_h)
        return Forcing(
            dt_s=float(dt_s),
            t_air_k=c_to_k(lin(self.t_air_c)),
            dew_c=np.minimum(lin(self.dew_c), lin(self.t_air_c)),
            wind10_ms=np.maximum(lin(self.wind10_ms), 0.0),
            dni=dni,
            dhi=dhi,
            ghi=ghi,
            sin_elev=sin_e,
            cos_elev=cos_e,
            solar_hour=hours_local,
            pm10=np.maximum(lin(self.pm10_ugm3), 0.0),
            precip_mm_h=np.maximum(rain, 0.0),
            p_pa=pressure_at_elevation(self.altitude_m),
        )

    def index_of(self, when, dt_s: float = 600.0) -> int:
        """Index on the forcing grid at or after a UTC time."""
        w = np.datetime64(when, "s")
        delta = float((w - self.times_utc[0]).astype("timedelta64[s]").astype(float))
        return int(np.clip(round(delta / dt_s), 0, len(self._grid(dt_s)) - 1))

    def summary(self) -> dict:
        return {
            "source": self.source,
            "label": self.label,
            "start_utc": str(self.times_utc[0]),
            "end_utc": str(self.times_utc[-1]),
            "t_air_max_c": float(np.max(self.t_air_c)),
            "pm10_max_ugm3": float(np.max(self.pm10_ugm3)),
            "wind10_max_ms": float(np.max(self.wind10_ms)),
            "notes": list(self.notes),
        }
