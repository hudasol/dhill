# Nav2 adapter

The adapter lets a robot that navigates with Nav2 follow Dhill decisions without changing its planner.

| Dhill decision | Command | Effect |
|---|---|---|
| GO | run | No speed limit from Dhill. |
| DERATE | limit | A `nav2_msgs/SpeedLimit` message with `percentage` true and the scale found by Dhill, between 10 and 99 percent. |
| PARK | park | A `std_msgs/Bool` true on `/dhill/park_request`. A supervisor node, or the operator, sends the robot to its shade pose. |

Design choices:

* PARK is not sent as a speed limit of zero, because a limit of zero may mean no limit to a Nav2
  controller. Confirm this for the installed Nav2 version.
* A command is published only when it changes by 5 percentage points or changes kind, so the robot is not
  commanded every period.
* If the Dhill service cannot be reached for longer than 30 minutes, the adapter issues a park request marked
  as a fail safe. A lost link therefore never looks like a GO. For a shorter outage the last command stays.
* The decision carries the evidence level of the profile. At L0 it reflects assumptions, not the robot.

Status. The mapping, the chatter filter and the stale data rule are unit tested without ROS
(`tests/test_nav2_adapter.py`). The ROS 2 node has not been run against a live Nav2 stack here. Test it in
simulation before a robot, and keep the robot's own hardware thermal protection active.

```
dhill serve --host 127.0.0.1 --port 8080
colcon build --packages-select dhill_nav2_adapter
ros2 launch dhill_nav2_adapter adapter.launch.py
```
