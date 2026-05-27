#!/usr/bin/env python3
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_name = 'auto_exploration'
    pkg_share_dir = get_package_share_directory(pkg_name)
    config_file_path = os.path.join(pkg_share_dir, 'config', 'exploration.yaml')

    explorer_node = Node(
        package=pkg_name,
        executable='exploration.py',  # 注意：这必须与 setup.py 中定义的 entry_point 名字一致
        name='auto_explorer',  # 节点名称，会覆盖代码里初始化的名字
        output='screen',  # 将节点的 get_logger() 输出直接打印到终端
        parameters=[config_file_path]  # 将 YAML 文件传递给节点
    )

    # 4. 返回 Launch 描述符
    return LaunchDescription([
        explorer_node
    ])