from launch import LaunchDescription
from launch_ros.actions import Node
import os

def generate_launch_description():
    home_dir = os.path.expanduser('~')
    absolute_output_dir = os.path.join(home_dir, 'ros_exported_data', 'laser_scan')
    data_sniffer_node = Node(
        package='data_sniffer',
        executable='data_sniffer',
        name='laserScan_sniffer',
        output='screen',
        parameters=[{
            'topic_name': '/scan',
            'msg_type': 'LaserScan',
            'output_dir': absolute_output_dir,
            'target_fps': 10.0
        }]
    )

    return LaunchDescription([
        data_sniffer_node
    ])