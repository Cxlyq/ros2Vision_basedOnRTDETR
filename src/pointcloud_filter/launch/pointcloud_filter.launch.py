import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_dir = get_package_share_directory('pointcloud_filter')
    pc_filter_config_path = os.path.join(pkg_dir, 'params', 'ros_laser_filter.yaml')

    return LaunchDescription([
        Node(
            package='laser_filters',
            executable='scan_to_scan_filter_chain',
            name='laser_filter',
            parameters=[pc_filter_config_path],
            # 话题重映射：输入 /scan，输出 /scan_filtered
            remappings=[
                ('scan', '/scan'),
                ('scan_filtered', '/scan_filtered')
            ],
            output='screen'
        )
    ])