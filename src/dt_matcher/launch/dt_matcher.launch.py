import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_name = 'dt_matcher'

    # 获取参数文件路径
    pkg_dir = get_package_share_directory(pkg_name)
    config_path = os.path.join(pkg_dir, 'config', 'dt_matcher.yaml')

    # 定义 dt_matcher 节点
    dt_matcher_node = Node(
        package=pkg_name,
        executable='dt_matcher',
        name='dt_matcher',
        output='screen',
        parameters=[config_path],
    )

    return LaunchDescription([
        dt_matcher_node
    ])