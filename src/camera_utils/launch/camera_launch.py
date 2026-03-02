from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # 1. 启动 usb_cam 节点
        Node(
            package='usb_cam',
            executable='usb_cam_node_exe',
            name='usb_cam',
            parameters=[{
                'video_device': '/dev/video2',
                'image_width': 2560,
                'image_height': 720,
                'pixel_format': 'mjpeg2rgb',
                'framerate': 30.0,
                'camera_name': 'stereo_camera'
            }]
        ),

        # 2. 启动拆分节点
        Node(
            package='camera_utils',
            executable='splitter',
            name='stereo_splitter',
            parameters=[{
                'input_topic': '/image_raw',
                'left_img_topic': '/camera/left/image_raw',
                'right_img_topic': '/camera/right/image_raw',
                'left_info_topic': '/camera/left/camera_info',
                'right_info_topic': '/camera/right/camera_info',
                'left_yaml_path': '/home/cx/Documents/codes/ros_vision/config/camera_info/left.yaml',
                'right_yaml_path': '/home/cx/Documents/codes/ros_vision/config/camera_info/right.yaml'
            }]
        )
    ])