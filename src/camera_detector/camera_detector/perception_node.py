import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image  # 导入ROS图像消息类型
from cv_bridge import CvBridge  # 导入ROS-OpenCV转换桥梁
import cv2  # 导入OpenCV


class PerceptionNode(Node):
    def __init__(self):
        # 1. 初始化节点，名字叫 'perception_node'
        super().__init__('perception_node')

        # 2. 创建转换器实例
        self.bridge = CvBridge()

        # 3. 创建订阅者 (Subscriber)
        # 语法: self.create_subscription(消息类型, 话题名, 回调函数, 队列长度)
        self.subscription = self.create_subscription(
            Image,  # 消息类型是什么？(提示：看上面的 import)
            'camera/image_raw',  # Gazebo 的相机话题名是什么？
            self.image_callback,  # 收到图后，交给哪个函数处理？(提示：是下面定义的那个函数)
            10  # QoS (队列长度)
        )

        self.get_logger().info("Perception Node has been started! Waiting for images...")

    def image_callback(self, msg):
        """
        这是回调函数，每次收到一张图就会被调用一次
        参数 msg: 就是 ROS 发过来的原始图像数据
        """
        try:
            # 4. 将 ROS 图像消息转换为 OpenCV 图像
            # 语法: self.bridge.imgmsg_to_cv2(消息对象, 目标编码)
            # 目标编码通常用 "bgr8" (蓝绿红 8位，这是 OpenCV 的标准格式)
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")

            # 5. (测试用) 在屏幕上显示图像
            cv2.imshow("Robot Camera View", cv_image)
            cv2.waitKey(1)  # 刷新窗口，必须有这句，否则窗口会卡死

        except Exception as e:
            self.get_logger().error(f"Error converting image: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = PerceptionNode()

    try:
        rclpy.spin(node)  # 让节点一直转圈，保持监听状态
    except KeyboardInterrupt:
        pass
    finally:
        # 销毁节点，释放资源
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()