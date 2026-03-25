import os
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # === 1. RTAB-Map 核心参数配置 ===
    parameters = [{
        'frame_id': 'base_link',  # 机器人的中心坐标系
        'use_sim_time': True,  # 极其重要：使用 Gazebo 的仿真时钟
        'subscribe_depth': True,  # 订阅深度图
        'subscribe_scan': True,  # 订阅 2D 激光雷达 (大大增强建图稳定性)
        'approx_sync': True,  # 允许图像、雷达、里程计时间戳有微小偏差
        'queue_size': 20,

        # 算法细节调优 (针对你的小车)
        'Grid/FromDepth': 'false',  # 使用雷达(/scan)生成2D栅格地图，而不是用深度图(更清晰)
        'Reg/Strategy': '1',  # 0=视觉特征, 1=ICP(雷达扫描匹配), 2=视觉+ICP。优先用雷达纠正里程计
        'RGBD/NeighborLinkRefining': 'true'  # 使用雷达对地图进行细化纠偏
    }]

    # === 2. 话题重映射 (将 TB4 的话题对接给 RTAB-Map) ===
    remappings = [
        ('rgb/image', '/oakd/rgb/preview/image_raw'),
        ('depth/image', '/oakd/rgb/preview/depth'),
        ('rgb/camera_info', '/oakd/rgb/preview/camera_info'),
        ('scan', '/scan'),
        ('odom', '/odom')
    ]

    # === 3. 定义 SLAM 建图节点 ===
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        output='screen',
        parameters=parameters,
        remappings=remappings,
        arguments=['-d']  # '-d' 表示每次启动都清空旧数据库，从头开始建新地图
    )

    # === 4. 定义 3D 可视化节点 (RTAB-Map 自带的 GUI) ===
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