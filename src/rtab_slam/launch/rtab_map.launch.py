from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # === 1. RTAB-Map 核心参数配置 ===
    parameters = [{
        'frame_id': 'base_link',  # 机器人的中心坐标系
        'use_sim_time': True,  # 使用 Gazebo 仿真时钟
        'subscribe_depth': True,  # 订阅深度图
        'subscribe_scan': True,  # 订阅 2D 激光雷达
        'approx_sync': True,  # 允许时间戳微小偏差
        'queue_size': 20,

        # 算法调优
        'Grid/FromDepth': 'false',  # 用雷达(/scan)建2D地图，比用深度图更清晰
        'Reg/Strategy': '1',  # 优先使用雷达(ICP)来纠正里程计
        'RGBD/NeighborLinkRefining': 'true'
    }]

    # === 2. 话题重映射 ===
    remappings = [
        ('rgb/image', '/oakd/rgb/preview/image_raw'),
        ('depth/image', '/oakd/rgb/preview/depth'),
        ('rgb/camera_info', '/oakd/rgb/preview/camera_info'),
        ('scan', '/scan'),
        ('odom', '/odom')
    ]

    # === 3. RTAB-Map 建图后端节点 ===
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        output='screen',
        parameters=parameters,
        remappings=remappings,
        arguments=['-d']  # '-d' = delete_db_on_start (每次启动都建新图)
    )

    # === 4. RTAB-Map 自带的 3D 可视化前端 ===
    rtabmap_viz = Node(
        package='rtabmap_viz',
        executable='rtabmap_viz',
        output='screen',
        parameters=parameters,
        remappings=remappings
    )

    return LaunchDescription([
        rtabmap_node,
        rtabmap_viz
    ])