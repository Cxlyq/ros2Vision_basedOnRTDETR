import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image  # 导入ROS图像消息类型
from cv_bridge import CvBridge  # 导入ROS-OpenCV转换桥梁
import cv2  # 导入OpenCV

import torch
import torchvision.transforms as T
from PIL import Image, ImageDraw, ImageFont
import numpy as np
try:
    from .external_models.RT_DETR_V2.src.core import YAMLConfig
    from .external_models.RT_DETR_V2.src.zoo.rtdetr.rtdetr import RTDETR
except ImportError as e:
    print(f"Import RT-DETR failed: {e}")
    raise e

from ai_msgs.msg import Detection, DetectionArray

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

        # 4. 创建发布者 (Publisher)
        self.publisher = self.create_publisher(
            DetectionArray,
            'brain/detections',
            10
        )
        self.get_logger().info("Perception Node has been started! Initializing vision model...")
        rt_detr_model = self.load_rt_detr_model()

    def load_rt_detr_model(self):
        self.get_logger().info("Loading vision model...")
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 自动拼接出权重文件的路径
        # 这样无论你把项目拷到哪里，它都能找到权重
        checkpoint_path = os.path.join(current_dir, "weights", "rtdetrv2_r50vd_6x_coco_full.pth")  # TODO: 更优雅的方式设定文件名(config文件)
        model_config = os.path.join(current_dir, "external_models", "RT_DETR_V2", "configs", "rtdetrv2", "rtdetrv2_r50vd_6x_coco.yml") # TODO: 更优雅的方式设定配置文件名(config文件)

        if not os.path.exists(checkpoint_path) or not os.path.isfile(checkpoint_path):
            self.get_logger().error(f"Cannot found checkpoint in  {checkpoint_path}")
            return None
            # TODO: 错误处理

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        CLASSES = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
            'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
            'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
            'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
            'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard',
            'cell phone',
            'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
            'hair drier', 'toothbrush'
        ]

        try:
            conf = YAMLConfig(model_config, resume=None)
            model = conf.model.to(device)
            model.eval()
        except Exception as model_build_err:
            self.get_logger().error(f"❌ Cannot build rt-detr model: {model_build_err}")
            return None

        # --- 2. 加载权重 ---
        self.get_logger().info(f"Loading checkpoint from {checkpoint_path}...")
        checkpoint = torch.load(checkpoint_path, map_location='cpu')

        # 智能提取 state_dict
        if 'ema' in checkpoint:
            self.get_logger().info("ℹ️ Using EMA weights")
            state_dict = checkpoint['ema']['module'] if 'module' in checkpoint['ema'] else checkpoint['ema']
        elif 'model' in checkpoint:
            self.get_logger().info("ℹ️ Using Model weights")
            state_dict = checkpoint['model']
        else:
            state_dict = checkpoint

        # 去除 module. 前缀
        new_state_dict = {}
        for k, v in state_dict.items():
            if k.startswith('module.'):
                new_state_dict[k[7:]] = v
            else:
                new_state_dict[k] = v

        msg = model.load_state_dict(new_state_dict, strict=False)
        self.get_logger().info(f"Weights loaded. Missing keys: {len(msg.missing_keys)}")
        return model

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