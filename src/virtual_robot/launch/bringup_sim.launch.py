import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. 获取包路径
    pkg_my_robot = get_package_share_directory('virtual_robot')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    
    xacro_file = os.path.join(pkg_my_robot, 'urdf', 'robot.xacro')

    # 2. 启动 Robot State Publisher (解析 xacro 文件并发布机器人 TF 树)
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': Command(['xacro ', xacro_file]),
            'use_sim_time': True  # 极其重要：告诉 ROS2 使用仿真时间
        }]
    )

    # 3. 启动 Ignition Gazebo (默认加载一个空世界，-r 表示直接运行不暂停)
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
    )

    # 4. 在 Gazebo 中生成小车模型 (Spawn Entity)
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=['-topic', 'robot_description',
                   '-name', 'my_stereo_robot',
                   '-z', '0.5'] # 在半空中生成，让它自然掉到地上
    )

    # 5. 启动 ROS-Ignition 桥接器 (打通次元壁的核心！)
    # 格式说明：/话题名@ROS2数据类型[Ignition数据类型 ([表示Ignition->ROS2, ]表示ROS2->Ignition )
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            # 仿真时钟 (Ignition -> ROS2)
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            # 速度控制 cmd_vel (ROS2 -> Ignition)
            '/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
            # 里程计 odom (Ignition -> ROS2)
            '/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
            # TF 树 (Ignition -> ROS2)
            '/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V',
            # 左相机图像 (Ignition -> ROS2)
            '/camera/left/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            # 右相机图像 (Ignition -> ROS2)
            '/camera/right/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
        ],
        output='screen'
    )

    return LaunchDescription([
        robot_state_publisher,
        gazebo,
        spawn_entity,
        bridge
    ])
