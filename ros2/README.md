# ROS 2 telemetry recorder

`dhill_recorder` samples temperature and power topics onto a fixed grid and writes
the CSV read by `dhill calibrate`. The recording logic lives in
`dhill.ros2_bridge.recorder.TelemetryRecorder` and is unit tested without ROS.
The ROS 2 node itself has **not** been run against a live ROS graph in this repository
(no ROS installation in CI); treat it as an integration starting point.

```
colcon build --packages-select dhill_recorder
ros2 run dhill_recorder recorder telemetry.csv
```
Topics are listed in the module docstring. Map your robot's topics with `ros2 topic remap`
or a small relay node.

## Nav2 adapter

`dhill_nav2_adapter` turns a Dhill decision into a Nav2 speed limit (DERATE) or a park request (PARK) and
fails safe to a park request if the Dhill service cannot be reached for longer than a configured time. The
mapping logic is `dhill.ros2_bridge.nav2_adapter` and is unit tested without ROS. The node has **not** been
run against a live Nav2 stack in this repository; test it in simulation first. See `docs/nav2-adapter.md`.

```
colcon build --packages-select dhill_nav2_adapter
ros2 launch dhill_nav2_adapter adapter.launch.py
```
