# Dhill (ظل)

Thermal and dust operating envelope intelligence for autonomous ground systems in hot arid environments.

Dhill answers one question for a robot, a place and an hour: should the robot work now, work slower, or
rest in the shade. Each answer is GO, DERATE or PARK, with the reasons, the component that binds, and the
evidence level of the robot profile behind it.

## Where the project stands

* All bundled robot profiles are illustrative and at evidence level **L0**. Nothing in this project has been
  validated against a real robot.
* Every test robot used in the experiments is a **synthetic** simulated robot from an independent model,
  and the results say how Dhill behaves against structural error, not how accurate it is on hardware.
* The next step toward evidence is an instrumented robot run, planned with Al Ain University. See the
  [pilot kit](pilot-kit.md) and the [roadmap](roadmap-to-v1.md).
* Dhill makes no compliance claim for any standard and implies no endorsement by any organisation.

## Where to start

| If you want to | Read |
|---|---|
| Understand the method and its limits | [Model card](model-card.md), [Known issues](known-issues.md) |
| See what was tested and what was found | [Results](results.md), [v0.8 predictions and results](prereg-results-v08.md) |
| Run Dhill on your own robot | [Pilot kit](pilot-kit.md), [Parameters](parameters.md) |
| Connect Dhill to a robot stack | [Edge integration](edge-integration.md), [REST API](api.md) |
| Plan a logging session | [Logging session quickstart](logging-session-quickstart.md), [Field test kit](field-test-kit.md) |

## Install

```
pip install dhill
dhill decide --profile ugv_medium_inspection --site al_ain --scenario heatwave
```

The package is not yet published on the Python Package Index. Until it is, install from a checkout with
`pip install .`.

Source code: <https://github.com/hudasol/dhill>. Licence: Apache 2.0.
