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
        'Grid/Sensor': '1',
        'Reg/Strategy': '1',  # 优先使用雷达(ICP)来纠正里程计
        'RGBD/NeighborLinkRefining': 'true',
        # 强制开启 3D 射线追踪与地面高度过滤
        'Grid/3D': "true",  # 强迫 RTAB-Map 在 3D 空间中计算雷达射线，而不是拍扁在 2D 里算
        'Grid/MaxGroundHeight': '0.15',  # 将距离地面 15 厘米以下的所有雷达点视为“地板”，直接剔除！
        'Grid/MaxObstacleHeight': '2.0',  # 忽略 2 米以上的天花板噪点
        # 开启基于半径的孤立噪点滤波
        'Grid/NoiseFilteringRadius': '0.08',  # 过滤半径 0.5 米
        'Grid/NoiseFilteringMinNeighbors': '4', # 如果一个黑点在 0.1 米半径内，周围没有至少 5 个黑点做伴，就判定它是“幽灵噪点”，直接抹除！
        # 限制雷达的有效建图距离
        'Grid/RangeMax': '5.0', # 雷达打得越远，打到地面的概率越高。限制只相信 5 米内的雷达数据。
        # 运动更新阈值
        'RGBD/LinearUpdate': "0.1",  # 小车平移超过 0.1 米，才把新的雷达数据融合进地图
        'RGBD/AngularUpdate': "0.1",  # 小车旋转超过 0.1 弧度（约5.7度），才融合数据
        # 开启射线追踪清除
        'Grid/RayTracing': 'true',
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