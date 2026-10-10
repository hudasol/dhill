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
