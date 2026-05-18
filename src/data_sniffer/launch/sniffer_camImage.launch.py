from launch import LaunchDescription
from launch_ros.actions import Node
import os


def generate_launch_description():
    home_dir = os.path.expanduser('~')

    # 为 RGB 和 Depth 分别创建独立的数据导出目录
    rgb_output_dir = os.path.join(home_dir, 'ros_exported_data', 'cam_rgb')
    depth_output_dir = os.path.join(home_dir, 'ros_exported_data', 'cam_depth')

    # 1. RGB 相机数据提取节点
    rgb_sniffer_node = Node(
        package='data_sniffer',
        executable='data_sniffer',
        name='rgbImage_sniffer',  # 自定义节点名，防止冲突
        output='screen',
        parameters=[{
            'topic_name': '/camera/color/image_raw',
            'msg_type': 'Image',
            'output_dir': rgb_output_dir,
            'target_fps': 10.0
        }]
    )

    # 2. Depth 深度图数据提取节点
    depth_sniffer_node = Node(
        package='data_sniffer',
        executable='data_sniffer',
        name='depthImage_sniffer',  # 自定义节点名，防止冲突
        output='screen',
        parameters=[{
            'topic_name': '/camera/depth/image_raw',
            'msg_type': 'Image',
            'output_dir': depth_output_dir,
            'target_fps': 10.0  # 补全了帧率控制参数
        }]
    )

    return LaunchDescription([
        rgb_sniffer_node,
        depth_sniffer_node
    ])