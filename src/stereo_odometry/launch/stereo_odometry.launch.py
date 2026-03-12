from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='rtabmap_odom',
            executable='stereo_odometry',
            name='stereo_odometry',
            output='screen',
            parameters=[{
                'frame_id': 'base_link',  # 机器人的基准坐标系
                'odom_frame_id': 'odom',  # 里程计坐标系名字
                'publish_tf': True,  # 发布 odom -> base_link 的变换
                'wait_for_transform': 0.2,  # 等待 TF 的时间
                'approx_sync': True,  # 如果左右目严格同步设为False，否则True
                'queue_size': 10,

                # --- 视觉里程计调优参数 (可选) ---
                'Odom/Strategy': '0',  # 0=Frame-to-Map (推荐), 1=Frame-to-Frame
                'Odom/GuessMotion': 'true',  # 假设运动模型，减少跟丢概率
                'Vis/MinInliers': '15',  # 至少需要多少个特征点才算有效匹配
                'GFTT/MinDistance': '5',  # 特征点提取的最小间距
                'GFTT/QualityLevel': '0.001',  # 特征点质量阈值
                # 增加视差搜索范围（默认是 128，改为 256 或更高）
                'Stereo/MaxDisparity': '256',
                # 光流法窗口大小，稍微调大一点可以增加鲁棒性
                'Vis/WinSize': '30',
            }],
            remappings=[
                # 订阅的话题 (左边是节点内部名，右边是你实际的话题名)
                ('left/image_rect', '/camera/left/image_rect'),
                ('right/image_rect', '/camera/right/image_rect'),
                ('left/camera_info', '/camera/left/camera_info'),
                ('right/camera_info', '/camera/right/camera_info'),
                # 发布的话题
                ('odom', '/odom')
            ]
        )
    ])