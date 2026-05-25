import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_name = 'dveformer'

    # 获取参数文件路径
    pkg_dir = get_package_share_directory(pkg_name)
    config_path = os.path.join(pkg_dir, 'config', 'dveformer.yaml')

    # 定义 DVEFormer 节点
    dveformer_node = Node(
        package=pkg_name,
        executable='simpleDVE.py',
        name='dveformer',
        output='screen',
        parameters=[config_path],
        # 由于在 simpleDVE.py 内部已经声明了话题参数，
        # 并通过 yaml 文件进行覆盖，所以这里不再写 remappings，
    )

    return LaunchDescription([
        dveformer_node
    ])