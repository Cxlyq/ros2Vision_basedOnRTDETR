import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction, GroupAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    # ==========================================
    # 1. 声明控制参数
    # ==========================================
    # 是否为仿真环境：'true' 或 'false'
    is_sim_arg = DeclareLaunchArgument(
        'is_sim', default_value='false',
        description='是否在仿真环境中运行 (true/false)'
    )

    # 工作模式：'manual'(手动), 'auto'(自动探图), 'semantic'(语义探图)
    mode_arg = DeclareLaunchArgument(
        'mode', default_value='manual',
        description='运行模式选择: manual, auto, semantic'
    )

    # 获取参数内容
    is_sim = LaunchConfiguration('is_sim')
    mode = LaunchConfiguration('mode')

    # 获取各个子功能包的路径
    # 假设你的所有启动脚本都收纳在或能索引到对应的功能包中
    pkg_hardware = get_package_share_directory('car_bringup')  # 示例，可以用你专门的bringup包
    pkg_gazebo = get_package_share_directory('turtlebot4_ignition_bringup')
    pkg_filter = get_package_share_directory('pointcloud_filter')
    pkg_rtab = get_package_share_directory('rtab_slam')
    pkg_nav2 = get_package_share_directory('nav2_tb4')
    pkg_explore = get_package_share_directory('auto_exploration')
    pkg_dveformer = get_package_share_directory('dveformer')

    # ==========================================
    # 2. 定义底层环境启动项 (第一阶段)
    # ==========================================

    # 【实体车情况】启动三个硬件驱动节点
    launch_hardware = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_hardware, 'launch', 'hardware_all.launch.py')),
        condition=UnlessCondition(is_sim)  # 当 is_sim 为 false 时启动
    )

    # 【仿真情况】启动 Gazebo & TB4
    launch_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_gazebo, 'launch', 'turtlebot4_ignition.launch.py')),
        condition=IfCondition(is_sim)  # 当 is_sim 为 true 时启动
    )

    # ==========================================
    # 3. 定义导航与核心底座启动项 (第二阶段 - 顺序延时)
    # ==========================================
    # 无论是仿真还是实体，底座核心启动顺序一致。
    # 为了保证Gazebo或底层硬件完全就绪、TF坐标系和雷达数据正常发布，采用延时策略。

    # (1) Laser Filter
    launch_laser_filter = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_filter, 'launch', 'pointcloud_filter.launch.py'))
    )
    # 放置在延时队列中，等待底层环境启动 5 秒后执行
    delay_laser_filter = TimerAction(period=5.0, actions=[launch_laser_filter])

    # (2) RTAB SLAM (依赖滤波后的点云/雷达)
    launch_rtab = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_rtab, 'launch', 'rtab_map.launch.py'))
    )
    # 等底层环境启动 8 秒后（即滤除器启动3秒后）执行
    delay_rtab = TimerAction(period=8.0, actions=[launch_rtab])

    # (3) Nav2 导航堆栈 (依赖建图和定位底座)
    launch_nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_nav2, 'launch', 'nav2_tb4.launch.py'))
    )
    # 等底层环境启动 12 秒后执行
    delay_nav2 = TimerAction(period=12.0, actions=[launch_nav2])

    # ==========================================
    # 4. 高层应用节点启动项 (第三阶段 - 根据 mode 参数条件启动)
    # ==========================================

    # 【自动探图模式】启动 auto_exploration
    launch_exploration = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_explore, 'launch', 'exploration.launch.py')),
        condition=IfCondition(PythonExpression(["'", mode, "' == 'auto'"]))
    )
    # 必须在导航完全就绪后启动，延时 18 秒
    delay_exploration = TimerAction(period=18.0, actions=[launch_exploration])

    # 【语义感知探图模式】启动 dveformer
    launch_dveformer = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_dveformer, 'launch', 'dveformer.launch.py')),
        condition=IfCondition(PythonExpression(["'", mode, "' == 'semantic'"]))
    )
    delay_dveformer = TimerAction(period=18.0, actions=[launch_dveformer])

    # 【语义感知探图模式】预留的 dt_matcher 节点
    # 同样限定在 mode == 'semantic' 并且在 dveformer 之后再延时启动
    # timer_dt_matcher = TimerAction(period=22.0, actions=[...], condition=...)

    # ==========================================
    # 5. 返回总描述符
    # ==========================================
    return LaunchDescription([
        is_sim_arg,
        mode_arg,

        # 第一阶段：环境与底层
        launch_hardware,
        launch_gazebo,

        # 第二阶段：底座导航流水线
        delay_laser_filter,
        delay_rtab,
        delay_nav2,

        # 第三阶段：应用算法
        delay_exploration,
        delay_dveformer
    ])