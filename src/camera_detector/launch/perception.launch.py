import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 1. 找到配置文件的路径
    # 注意：这里找的是 install 目录下的 share，不是源码目录
    package_name = 'camera_detector'
    config_file_path = os.path.join(
        get_package_share_directory(package_name),
        'config',
        'rtdetr_config.yaml'
    )

    # 2. 定义节点
    perception_node = Node(
        package=package_name,
        executable='perception_node',
        name='perception_node',
        output='screen',
        emulate_tty=True, # 可以在终端显示彩色日志
        parameters=[config_file_path] # 加载 YAML 配置
    )

    return LaunchDescription([
        perception_node
    ])