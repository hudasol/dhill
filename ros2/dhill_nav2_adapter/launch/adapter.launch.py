from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="dhill_nav2_adapter",
                executable="adapter",
                parameters=[
                    {
                        "dhill_url": "http://127.0.0.1:8080",
                        "profile": "ugv_medium_inspection",
                        "site": "abu_dhabi",
                        "period_s": 300.0,
                    }
                ],
            )
        ]
    )
