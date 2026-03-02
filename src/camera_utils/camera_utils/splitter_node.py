import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import yaml


class StereoSplitterNode(Node):
    def __init__(self):
        super().__init__('stereo_splitter_node')

        # 声明参数，方便在 launch 文件中修改
        self.declare_parameter('input_topic', '/image_raw')
        self.declare_parameter('left_img_topic', '/camera/left/image_raw')
        self.declare_parameter('right_img_topic', '/camera/right/image_raw')
        self.declare_parameter('left_info_topic', '/camera/left/camera_info')
        self.declare_parameter('right_info_topic', '/camera/right/camera_info')
        self.declare_parameter('left_yaml_path', '/home/cx/Documents/codes/ros_vision/config/camera_info/left.yaml')
        self.declare_parameter('right_yaml_path', '/home/cx/Documents/codes/ros_vision/config/camera_info/right.yaml')

        input_topic = self.get_parameter('input_topic').get_parameter_value().string_value

        # 订阅
        self.subscription = self.create_subscription(
            Image,
            input_topic,
            self.listener_callback,
            10
        )

        # 发布
        left_img_topic = self.get_parameter('left_img_topic').get_parameter_value().string_value
        right_img_topic = self.get_parameter('right_img_topic').get_parameter_value().string_value
        left_info_topic = self.get_parameter('left_info_topic').value
        right_info_topic = self.get_parameter('right_info_topic').value
        left_yaml = self.get_parameter('left_yaml_path').value
        right_yaml = self.get_parameter('right_yaml_path').value

        self.left_info_msg = self.load_camera_info(left_yaml)
        self.right_info_msg = self.load_camera_info(right_yaml)

        self.pub_left_img = self.create_publisher(
            Image,
            left_img_topic,
            10
        )

        self.pub_right_img = self.create_publisher(
            Image,
            right_img_topic,
            10
        )

        self.pub_left_info = self.create_publisher(
            CameraInfo,
            left_info_topic,
            10
        )
        self.pub_right_info = self.create_publisher(
            CameraInfo,
            right_info_topic,
            10
        )

        self.bridge = CvBridge()
        self.get_logger().info(f'Splitter Node Started. Listening on {input_topic}')

    def load_camera_info(self, yaml_path):
        """解析 ROS 格式的 calibration yaml 文件"""
        info = CameraInfo()
        try:
            with open(yaml_path, "r") as file_handle:
                calib_data = yaml.safe_load(file_handle)

            # 填充 CameraInfo 数据
            info.width = calib_data['image_width']
            info.height = calib_data['image_height']
            info.distortion_model = calib_data.get('distortion_model', 'plumb_bob')

            # ROS yaml 中的矩阵通常存储在 'data' 字段中
            info.k = calib_data['camera_matrix']['data']
            info.d = calib_data['distortion_coefficients']['data']
            info.r = calib_data['rectification_matrix']['data']
            info.p = calib_data['projection_matrix']['data']

            self.get_logger().info(f"Successfully loaded {yaml_path}")
            return info

        except Exception as e:
            self.get_logger().warn(f"Failed to load yaml: {yaml_path}. Error: {e}")
            self.get_logger().warn("Will publish empty CameraInfo!")
            return CameraInfo()

    def listener_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            height, width, _ = cv_image.shape
            width_half = width // 2

            # 裁剪
            right_image = cv_image[:, :width_half]
            left_image = cv_image[:, width_half:]

            # --- 构建消息 ---
            # 关键点：Frame ID 必须对应。
            # 这里的 frame_id 需要和 TF 树中的定义一致
            left_frame_id = "camera_left_link"
            right_frame_id = "camera_right_link"

            # 1. 左相机图像消息
            left_img_msg = self.bridge.cv2_to_imgmsg(left_image, encoding='bgr8')
            left_img_msg.header = msg.header
            left_img_msg.header.frame_id = left_frame_id

            # 2. 右相机图像消息
            right_img_msg = self.bridge.cv2_to_imgmsg(right_image, encoding='bgr8')
            right_img_msg.header = msg.header
            right_img_msg.header.frame_id = right_frame_id

            # 3. 左相机内参消息
            self.left_info_msg.header = left_img_msg.header  # 必须完全同步

            # 4. 右相机内参消息
            self.right_info_msg.header = right_img_msg.header  # 必须完全同步

            # 5. 发布
            self.pub_left_img.publish(left_img_msg)
            self.pub_left_info.publish(self.left_info_msg)

            self.pub_right_img.publish(right_img_msg)
            self.pub_right_info.publish(self.right_info_msg)

        except Exception as e:
            self.get_logger().error(f'Error processing image: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = StereoSplitterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as unknown_err:
        node.get_logger().error(f"Unknown exception: {unknown_err}")
    finally:
        # 销毁节点，释放资源
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print("\n\033[92m[Cam splitter Node] [Info] Exited Cleanly.\033[0m")  # 绿色字体提示

if __name__ == '__main__':
    main()