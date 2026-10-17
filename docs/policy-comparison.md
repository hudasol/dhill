# Does the envelope beat the rules operators use today?

Run: `python examples/policy_comparison.py` (raw output: `examples/policy_comparison_output.txt`).

**Setup.** A hidden "true" robot is hotter than the L0 profile assumes (absorptance 0.52 vs 0.40,
shell interior conductance 14 vs 18 W/K, shell heat capacity 24 kJ/K, changed from the profile value). Each policy picks an operating
scale for 24 hourly missions (1 h, drive mode) from the *forecast and the L0 profile only*. The scorer then runs the
true robot through 200 weather realisations whose forecast error (ΔT σ 2 K, irradiance 15 %, wind 30 %) is
**heavier than the engine assumes** (1.5 K / 10 % / 25 %). A *violation* is any component above its hard limit during
a mission. A *risky hour* is an operated hour with violation probability above 5 %.

| Site / scenario | Policy | Productive h | Mean P(violate) | Risky hours |
|---|---|---:|---:|---:|
| Abu Dhabi / summer clear | Air ≤ 45 °C | 24.0 | 8.3 % | 6 |
| | Air ≤ 40 °C | 14.0 | 0.0 % | 0 |
| | Midday ban 12:30–15:00 | 21.0 | 3.5 % | 3 |
| | Envelope, no uncertainty | 22.2 | 2.7 % | 6 |
| | **Envelope L0** | 15.6 | 0.0 % | 0 |
| | **Envelope L2 (calibrated)** | 14.6 | 0.0 % | 0 |
| Sweihan / heatwave | Air ≤ 45 °C | 14.0 | 0.6 % | 1 |
| | Air ≤ 40 °C | 10.0 | 0.0 % | 0 |
| | Midday ban 12:30–15:00 | 21.0 | 18.2 % | 6 |
| | Envelope, no uncertainty | 17.0 | 1.7 % | 3 |
| | **Envelope L0** | 13.3 | 0.0 % | 0 |
| | **Envelope L2 (calibrated)** | 12.7 | 0.0 % | 0 |
| Dubai / humid coastal | Air ≤ 45 °C | 24.0 | 6.9 % | 7 |
| | Air ≤ 40 °C | 18.0 | 1.6 % | 2 |
| | Midday ban 12:30–15:00 | 21.0 | 3.2 % | 4 |
| | Envelope, no uncertainty | 22.6 | 2.9 % | 7 |
| | **Envelope L0** | 15.5 | 0.0 % | 0 |
| | **Envelope L2 (calibrated)** | 14.8 | 0.0 % | 0 |

## Honest reading

1. **Uncertainty handling is what matters.** The same engine without uncertainty (σ = 0) violates limits in every
   case (up to 7 risky hours). With it, zero risky hours in all three cases, even though reality was harsher than assumed.
2. **Common rules are not safe by construction.** The midday ban was the worst in the Sweihan heatwave (18.2 % mean
   violation probability) because dangerous hours are not only midday. Air ≤ 45 °C was unsafe in two of three cases.
3. **A conservative threshold is competitive.** Air ≤ 40 °C had zero risky hours in two cases and *beat*
   the envelope on productive hours in Dubai (18.0 h vs 15.5 h) while having 2 risky hours there. In Abu Dhabi and Sweihan
   it was safe but less productive than the envelope (14.0 vs 15.6 h; 10.0 vs 13.3 h). **The envelope's edge here is a guarantee with reason
   (per hour, per component, with its binding constraint), not a large productivity gain.**
4. **Calibration (L2) made the engine slightly more conservative here**, because the true robot is hotter than the L0
   assumptions. That is the correct direction, but calibration did not buy productive hours in this test.
5. **A caveat that cuts against the result:** the engine and the hidden robot share the same model structure, and the
   telemetry is synthetic. Real robots have unmodelled physics. This shows the method behaves as designed; it is
   not field evidence. The preregistered instrumented run (`docs/field-test-kit.md`) is the real test.
