# Parameter reference

Generated from `src/dhill/profiles/registry.py` by `scripts/gen_parameters_doc.py`. Do not edit by hand.

Monte Carlo spread by provenance (relative one-sigma, lognormal): measured 2%, datasheet 5%, textbook 10%, assumption 25%, calibrated 5%. A profile may override a spread with `rel_sigma` (for example cell counts use 0).

| Key | Unit | Bounds | Optional (default) | Meaning |
|---|---|---|---|---|
| `geometry.length_m` | m | 0.05 to 6 | no | Body length |
| `geometry.width_m` | m | 0.05 to 4 | no | Body width |
| `geometry.height_m` | m | 0.03 to 3 | no | Body height |
| `geometry.char_length_m` | m | 0.03 to 3 | yes (0) | Characteristic length for outer convection |
| `surface.alpha_clean` | - | 0.05 to 0.98 | no | Solar absorptance of the clean outer surface |
| `surface.alpha_dust` | - | 0.05 to 0.98 | no | Solar absorptance of a fully dust-covered surface |
| `surface.emissivity` | - | 0.03 to 0.98 | no | Longwave emissivity of the outer surface |
| `surface.dust_m0_g_m2` | g/m2 | 0.1 to 50 | no | Dust loading at which about 63% of the surface is covered |
| `shell.heat_capacity_j_k` | J/K | 100 to 500000 | no | Heat capacity of the outer skin |
| `interior.heat_capacity_j_k` | J/K | 100 to 500000 | no | Heat capacity of interior air and chassis |
| `battery.heat_capacity_j_k` | J/K | 100 to 500000 | no | Heat capacity of the battery pack |
| `compute.heat_capacity_j_k` | J/K | 10 to 50000 | no | Heat capacity of the compute module and heat-sink |
| `lidar.heat_capacity_j_k` | J/K | 10 to 50000 | no | Heat capacity of the LiDAR housing |
| `motors.heat_capacity_j_k` | J/K | 50 to 200000 | no | Heat capacity of the motors |
| `coupling.ua_shell_interior_w_k` | W/K | 0.1 to 500 | no | Shell to interior conductance |
| `coupling.ua_battery_interior_w_k` | W/K | 0.05 to 200 | no | Battery to interior conductance |
| `coupling.ua_compute_interior_w_k` | W/K | 0.05 to 200 | no | Compute heat-sink to interior conductance (clean) |
| `coupling.ua_lidar_interior_w_k` | W/K | 0.01 to 50 | no | LiDAR to interior conductance |
| `coupling.ua_lidar_ambient_w_k` | W/K | 0.01 to 50 | no | LiDAR housing to ambient conductance |
| `coupling.ua_motors_interior_w_k` | W/K | 0.01 to 100 | no | Motors to interior conductance |
| `coupling.ua_motors_ambient_w_k` | W/K | 0.01 to 100 | no | Motors to ambient and ground conductance |
| `coupling.h_bottom_w_m2k` | W/m2K | 1 to 100 | no | Underside to ground coupling (convective + radiative + contact) |
| `coupling.vent_flow_m3_s` | m3/s | 0 to 1 | yes (0) | Filtered ventilation flow when clean (0 = sealed) |
| `coupling.filter_ref_g_m2` | g/m2 | 0.1 to 100 | yes (5) | Dust loading at which filter flow and heat-sink conductance halve |
| `battery.cells_series` | - | 1 to 200 | no | Cells in series |
| `battery.cells_parallel` | - | 1 to 100 | no | Cells in parallel |
| `battery.cell_capacity_ah` | Ah | 0.5 to 300 | no | Capacity per cell |
| `battery.cell_resistance_25c_ohm` | ohm | 0.0001 to 0.5 | no | DC resistance per cell at 25 degC |
| `battery.resistance_ea_j_mol` | J/mol | 0 to 60000 | no | Activation energy of resistance |
| `battery.ocv_v0` | V | 2 to 4 | no | Linearised cell open-circuit voltage at 0% state of charge |
| `battery.ocv_slope` | V | 0 to 2 | no | Cell open-circuit voltage rise from 0% to 100% |
| `battery.max_discharge_c_rate` | 1/h | 0.1 to 20 | no | Maximum continuous discharge rate |
| `battery.ageing_ea_j_mol` | J/mol | 10000 to 100000 | no | Activation energy of capacity ageing |
| `compute.nominal_power_w` | W | 0.1 to 500 | no | Compute power at full mission rate |
| `compute.min_power_fraction` | - | 0.05 to 1 | no | Compute power fraction at the minimum derate scale |
| `compute.die_rise_k_per_w` | K/W | 0 to 5 | no | Die temperature rise above the module node per watt |
| `lidar.power_w` | W | 0 to 100 | no | LiDAR electrical power |
| `lidar.exposed_area_m2` | m2 | 0 to 0.5 | no | Sun-exposed LiDAR area |
| `lidar.alpha` | - | 0.05 to 0.98 | no | LiDAR housing solar absorptance |
| `lidar.range_clear_m` | m | 0.1 to 500 | no | Clear-air detection range for the reference target |
| `motors.loss_fraction_in_motor` | - | 0 to 1 | no | Share of drivetrain losses dissipated in the motor node |
| `motors.drive_efficiency` | - | 0.2 to 0.98 | no | Electrical to mechanical efficiency of the drivetrain |
| `power.comms_w` | W | 0 to 200 | no | Communications and housekeeping load |
| `power.standby_w` | W | 0 to 200 | no | Parked standby electrical load |
| `power.dcdc_efficiency` | - | 0.5 to 0.99 | no | Power-conversion efficiency |
| `power.payload_heat_fraction` | - | 0 to 1 | no | Share of payload power dissipated inside the body |
| `cooling.capacity_w` | W | 0 to 2000 | yes (0) | Maximum active cooling power (0 = none) |
| `cooling.cop` | - | 0.2 to 6 | yes (1.5) | Coefficient of performance of active cooling |
| `cooling.setpoint_c` | degC | 15 to 60 | yes (40) | Interior cooling set-point |
| `cooling.gain_w_k` | W/K | 1 to 200 | yes (20) | Proportional gain of the cooling controller |
| `perception.nominal_speed_ms` | m/s | 0.05 to 30 | no | Nominal mission speed |
| `perception.decel_ms2` | m/s2 | 0.1 to 10 | no | Safe deceleration |
| `perception.reaction_s` | s | 0 to 5 | no | System reaction time |
| `perception.margin_m` | m | 0 to 20 | no | Stopping-distance safety margin |
| `environment.albedo` | - | 0 to 0.9 | no | Ground shortwave reflectance |
| `environment.ground_rise_k_per_kw_m2` | K per kW/m2 | 0 to 60 | no | Ground surface temperature rise above air per kW/m2 of sun |
| `environment.wind_exponent` | - | 0.05 to 0.5 | no | Wind-profile power-law exponent |
| `environment.deposition_velocity_m_s` | m/s | 1e-05 to 0.1 | no | Dust deposition velocity |
| `environment.rain_clear_mm_h` | mm/h | 0.1 to 20 | no | Rain rate that washes surfaces clean |
| `environment.mass_ext_eff_m2_g` | m2/g | 0.05 to 5 | no | Mass-extinction efficiency of airborne dust |
