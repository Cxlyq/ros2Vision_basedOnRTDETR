from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.actions import Node

def generate_launch_description():
    # 参数定义
    disparity_range_arg = DeclareLaunchArgument(
        'disparity_range', default_value='128',  # 建议改大一点，便于近距离测试
        description='Stereo disparity range'
    )

    # 1. 定义 base_link 到 左相机 (假设重合，根据实际安装位置修改)
    # 参数顺序: x y z yaw pitch roll parent_frame child_frame
    tf_base_to_left = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_to_left_tf',
        arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'camera_left_link']
    )

    # 2. 定义 左相机 到 右相机 (基线)
    # 假设你的双目间距是 6cm (0.06m)，右相机在左相机的 -X 方向 (取决于坐标系定义)
    # 如果点云分层或不对劲，把 0.06 改成 -0.06
    tf_left_to_right = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='left_to_right_tf',
        arguments=['0.06', '0', '0', '0', '0', '0', 'camera_left_link', 'camera_right_link']
    )


    # 3. 定义组件容器
    # 这是一个高性能的容器，我们在里面加载3个节点：左校正、右校正、视差计算
    container = ComposableNodeContainer(
        name='stereo_container',
        namespace='camera',
        package='rclcpp_components',
        executable='component_container',
        composable_node_descriptions=[
            # 1. 左眼畸变校正节点 (Rectify Node Left)
            ComposableNode(
                package='image_proc',
                plugin='image_proc::RectifyNode',
                name='left_rectify_node',
                namespace='camera/left',  # 放在这个空间下
                parameters=[{'output_message_age_limit': 10}],
                remappings=[
                    ('image', '/camera/left/image_raw'),  # 输入：Splitter
                    ('camera_info', '/camera/left/camera_info'),  # 输入：Splitter
                    ('image_rect', '/camera/left/image_rect')  # 输出：标准校正图
                ]
            ),
            # 2. 右眼畸变校正节点 (Rectify Node Right)
            ComposableNode(
                package='image_proc',
                plugin='image_proc::RectifyNode',
                name='right_rectify_node',
                namespace='camera/right',
                parameters=[{'output_message_age_limit': 10}],
                remappings=[
                    ('image', '/camera/right/image_raw'),
                    ('camera_info', '/camera/right/camera_info'),
                    ('image_rect', '/camera/right/image_rect')
                ]
            ),
            # 3. 视差计算节点 (Disparity Node)
            ComposableNode(
                package='stereo_image_proc',
                plugin='stereo_image_proc::DisparityNode',
                name='disparity_node',
                namespace='camera',
                parameters=[{
                    'stereo_algorithm': 1,  # SGBM
                    'disparity_range': LaunchConfiguration('disparity_range'),
                    'min_disparity': 1,
                    'correlation_window_size': 15,  # 稍微调大一点，图像更稳
                    'uniqueness_ratio': 15.0,
                    'speckle_size': 100,  # 过滤掉小的噪点块
                    'speckle_range': 4,
                    'approximate_sync': False,  # 你有完美同步
                    'queue_size': 10
                }],
                remappings=[
                    ('left/image_rect', '/camera/left/image_rect'),  # 输入左
                    ('right/image_rect', '/camera/right/image_rect'),  # 输入右
                    ('left/camera_info', '/camera/left/camera_info'),  # 输入左参
                    ('right/camera_info', '/camera/right/camera_info'),  # 输入右参
                    ('disparity', '/camera/disparity'),  # 输出视差
                    ('points2', '/camera/points2')  # 输出点云
                ]
            ),
            # 4. 点云生成 (生成 PointCloud2)
            ComposableNode(
                package='stereo_image_proc',
                plugin='stereo_image_proc::PointCloudNode',
                name='point_cloud_node',
                namespace='camera',
                parameters=[{
                    'approximate_sync': True,
                    'queue_size': 10,
                    'use_color': True,  # 生成彩色点云
                }],
                remappings=[
                    ('left/image_rect_color', '/camera/left/image_rect'),  # 用校正后的图做颜色
                    ('disparity', '/camera/disparity'),  # 用刚才生成的视差
                    ('left/camera_info', '/camera/left/camera_info'),
                    ('right/camera_info', '/camera/right/camera_info'),
                    ('points2', '/camera/points2')
                ]
            )
        ],
        output='screen',
    )

    return LaunchDescription([
        disparity_range_arg,
        tf_base_to_left,  # 启动 TF
        tf_left_to_right,  # 启动 TF
        container
    ])