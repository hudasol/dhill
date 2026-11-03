from setuptools import setup

package_name = "dhill_nav2_adapter"
setup(
    name=package_name,
    version="0.8.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/adapter.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={"console_scripts": ["adapter = dhill_nav2_adapter.node:main"]},
)
