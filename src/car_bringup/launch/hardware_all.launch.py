import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
# 核心：引入 Python 和 XML 两种不同的解析源
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource

def generate_launch_description():
    # 1. 获取原厂各个底层硬件功能包的 share 路径
    pkg_camera = get_package_share_directory('astra_camera')
    pkg_lidar = get_package_share_directory('lslidar_driver')
    pkg_chassis = get_package_share_directory('turn_on_wheeltec_robot')

    # 2. 包装奥比中光深度相机
    launch_camera = IncludeLaunchDescription(
        XMLLaunchDescriptionSource(
            os.path.join(pkg_camera, 'launch', 'gemini.launch.xml')
        )
    )

    # 3. 包装镭神激光雷达
    launch_lidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_lidar, 'launch', 'lsn10_launch.py')
        )
    )

    # 4. 包装轮趣底盘
    launch_chassis = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_chassis, 'launch', 'turn_on_wheeltec_robot.launch.py')
        )
    )

    # 5. 并行启动所有硬件驱动
    return LaunchDescription([
        launch_camera,
        launch_lidar,
        launch_chassis
    ])