import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    package_name = 'estimation'
    config_file_pth = os.path.join(
        get_package_share_directory(package_name),
        'config',
        'estimation_params.yaml'
    )

    estimation_node = Node(
        package=package_name,
        executable='estimation_node',
        name='estimation_node',
        output='screen',
        emulate_tty=True,
        parameters=[config_file_pth]
    )

    return LaunchDescription([
        estimation_node
    ])