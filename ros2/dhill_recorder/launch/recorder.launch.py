from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    return LaunchDescription(
        [
            ExecuteProcess(
                cmd=["ros2", "run", "dhill_recorder", "recorder", "telemetry.csv"], output="screen"
            )
        ]
    )
