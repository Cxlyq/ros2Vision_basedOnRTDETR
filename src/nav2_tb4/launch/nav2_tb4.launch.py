import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 获取参数文件路径
    pkg_dir = get_package_share_directory('nav2_tb4')
    nav2_params_path = os.path.join(pkg_dir, 'params', 'nav2_slam_params.yaml')

    # 定义我们要启动的 Nav2 生命周期节点（剔除了 map_server 和 amcl）
    lifecycle_nodes =['controller_server',
                       'planner_server',
                       'behavior_server',
                       'bt_navigator',
                       'waypoint_follower']

    # 映射 cmd_vel 话题
    remappings =[('/cmd_vel', '/cmd_vel')]

    return LaunchDescription([
        # 1. 局部控制器 (DWB)
        Node(
            package='nav2_controller',
            executable='controller_server',
            output='screen',
            parameters=[nav2_params_path],
            remappings=remappings),

        # 2. 全局规划器 (NavFn)
        Node(
            package='nav2_planner',
            executable='planner_server',
            name='planner_server',
            output='screen',
            parameters=[nav2_params_path]),

        # 3. 恢复行为服务器 (清除代价地图、旋转脱困等)
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            name='behavior_server',
            output='screen',
            parameters=[nav2_params_path],
            remappings=remappings),

        # 4. 行为树导航器
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            name='bt_navigator',
            output='screen',
            parameters=[nav2_params_path]),

        # 5. 航点跟随器
        Node(
            package='nav2_waypoint_follower',
            executable='waypoint_follower',
            name='waypoint_follower',
            output='screen',
            parameters=[nav2_params_path]),

        # 6. 生命周期管理器 (至关重要：按顺序激活以上所有节点)
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_navigation',
            output='screen',
            parameters=[{'use_sim_time': True},
                        {'autostart': True},
                        {'node_names': lifecycle_nodes}])
    ])