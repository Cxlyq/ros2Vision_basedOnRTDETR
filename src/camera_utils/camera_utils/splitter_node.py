import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class StereoSplitterNode(Node):
    def __init__(self):
        super().__init__('stereo_splitter_node')

        # 声明参数，方便在 launch 文件中修改
        self.declare_parameter('input_topic', '/image_raw')
        self.declare_parameter('left_topic', '/camera/left/image_raw')
        self.declare_parameter('right_topic', '/camera/right/image_raw')

        input_topic = self.get_parameter('input_topic').get_parameter_value().string_value

        # 订阅
        self.subscription = self.create_subscription(
            Image,
            input_topic,
            self.listener_callback,
            10
        )

        # 发布
        left_topic = self.get_parameter('left_topic').get_parameter_value().string_value
        right_topic = self.get_parameter('right_topic').get_parameter_value().string_value

        self.publisher_left = self.create_publisher(
            Image,
            left_topic,
            10
        )

        self.publisher_right = self.create_publisher(
            Image,
            right_topic,
            10
        )

        self.bridge = CvBridge()
        self.get_logger().info(f'Splitter Node Started. Listening on {input_topic}')

    def listener_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            height, width, _ = cv_image.shape
            width_half = width // 2

            # 裁剪
            right_image = cv_image[:, :width_half]
            left_image = cv_image[:, width_half:]

            # 发布左图
            left_msg = self.bridge.cv2_to_imgmsg(left_image, encoding='bgr8')
            left_msg.header = msg.header
            left_msg.header.frame_id = "camera_left_link"
            self.publisher_left.publish(left_msg)

            # 发布右图
            right_msg = self.bridge.cv2_to_imgmsg(right_image, encoding='bgr8')
            right_msg.header = msg.header
            right_msg.header.frame_id = "camera_right_link"
            self.publisher_right.publish(right_msg)

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