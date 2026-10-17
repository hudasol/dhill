# Architecture

```
Weather (Open-Meteo | CSV | synthetic) --> Weather --> Forcing (uniform grid, solar geometry)
Robot profile (YAML, provenance per parameter) --> ThermalParams (Monte Carlo batch)
                                   |
        Envelope engine: soak -> mission -> risk quantile -> best scale -> shade -> look-ahead
                                   |
      Decision / Timeline  -->  Planner (MILP)  -->  CLI | REST API | dashboard
Telemetry CSV (ROS 2 recorder) --> Calibration (least squares, CIs, hold-out) --> calibrated profile (L2)
```

| Module | Responsibility |
|---|---|
| `physics/` | Pure numerical models: air properties, solar, convection, radiation, battery, dust and LiDAR range, six node thermal network |
| `profiles/` | Parameter registry (units, bounds), Pydantic schema, YAML loader, built in L0 profiles |
| `weather/` | Weather container and providers; conversion to solver forcing |
| `envelope.py` | Decision logic with Monte Carlo risk |
| `planner.py` | Block scheduling MILP and fixed shift baseline |
| `calibrate.py` | Parameter fitting, synthetic telemetry generator |
| `api/`, `web/` | FastAPI service and offline dashboard |
| `ros2_bridge/`, `ros2/` | Telemetry recorder |

## Design decisions
- **Batch first solver.** One `simulate` call integrates every (start time, scale, shade, Monte Carlo sample) combination with a batched 6x6 solve, so a full day with uncertainty runs in seconds on a laptop.
- **Backward Euler with lagged coefficients.** Unconditionally stable for the stiff network. An energy balance residual diagnostic is tested to numerical zero.
- **Provenance is data.** Every parameter carries a source tag; the tag sets its Monte Carlo spread and is shown in every decision as the share of assumption parameters.
- **Conservative by construction.** Decisions use a risk quantile (default 95%) of the peak, a per component margin below the hard limit, a parked soak initial condition, and a state of charge reserve.
- **Offline first.** No cloud dependency; live weather is optional and fails explicitly.
