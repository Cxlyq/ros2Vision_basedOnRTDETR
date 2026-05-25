from launch import LaunchDescription
from launch_ros.actions import Node
import os
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # === 1. RTAB-Map 核心参数配置 ===
    pkg_dir = get_package_share_directory('rtab_slam')
    rtabmap_config_path = os.path.join(pkg_dir, 'params', 'rtab_map_params.yaml')
    parameters = [rtabmap_config_path]

    # === 2. 话题重映射 ===
    remappings = [
        ('rgb/image', '/camera/color/image_raw'),
        ('depth/image', '/camera/depth/image_raw'),
        ('rgb/camera_info', '/camera/color/camera_info'),
        ('scan', '/scan_filtered'),
        ('odom', '/odom_combined')
    ]

    # === 3. RTAB-Map 建图后端节点 ===
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=parameters,
        remappings=remappings,
        arguments=['-d']  # '-d' = delete_db_on_start (每次启动都建新图)
    )

    # === 4. RTAB-Map 自带的 3D 可视化前端 ===
    rtabmap_viz = Node(
        package='rtabmap_viz',
        executable='rtabmap_viz',
        name='rtabmap_viz',
        output='screen',
        parameters=parameters,
        remappings=remappings
    )

    return LaunchDescription([
        rtabmap_node,
        rtabmap_viz
    ])