import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image  # 导入ROS图像消息类型
from cv_bridge import CvBridge  # 导入ROS-OpenCV转换桥梁
import cv2  # 导入OpenCV

import torch
import torchvision.transforms as T
from PIL import Image as PILImage

try:
    from .external_models.RT_DETR_V2.src.core import YAMLConfig
    from .external_models.RT_DETR_V2.src.zoo.rtdetr.rtdetr import RTDETR
except ImportError as import_err:
    print(f"Import RT-DETR failed: {import_err}")
    raise import_err

from ai_msgs.msg import Detection, DetectionArray

class PerceptionNode(Node):
    def __init__(self):
        # 1. 初始化节点，名字叫 'perception_node'
        super().__init__('perception_node')

        # 2. 声明参数 (Elegance: 允许通过外部配置修改参数)
        # 声明一个名为 'conf_threshold' 的参数，默认值 0.5
        self.declare_parameter('conf_threshold', 0.5)
        # 声明类别列表，这里给一个默认的 COCO 列表，但可以在 Launch 文件里覆盖
        self.declare_parameter('class_names', [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
            'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
            'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
            'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
            'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard',
            'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
            'teddy bear', 'hair drier', 'toothbrush'
        ])
        self.declare_parameter('weights_file', 'rtdetrv2_r50vd_6x_coco_full.pth')
        self.declare_parameter('config_file', 'rtdetrv2_r50vd_6x_coco.yml')

        # 获取参数值
        self.conf_threshold = self.get_parameter('conf_threshold').value
        self.classes = self.get_parameter('class_names').value
        self.get_logger().info(f"Loaded {len(self.classes)} classes. Confidence Threshold: {self.conf_threshold}")

        # 3. 创建转换器实例
        self.bridge = CvBridge()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.transforms = T.Compose([
            T.Resize((640, 640)),
            T.ToTensor(),
            # RT-DETR 全系列都使用 ImageNet 标准归一化
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        # 4. 初始化模型，加载权重
        self.get_logger().info("Initializing vision model...")
        try:
            self.rt_detr_model = self.load_rt_detr_model()
        except Exception as model_err:
            self.get_logger().error(f"Vision model loaded error! {model_err}")
            raise model_err
        self.get_logger().info("Vision model has been installed! Initializing perception node... ")

        # 5. 创建订阅者 (Subscriber)
        # 语法: self.create_subscription(消息类型, 话题名, 回调函数, 队列长度)
        self.subscription = self.create_subscription(
            Image,  # 消息类型是什么？(提示：看上面的 import)
            '/camera/image_raw',  # Gazebo 的相机话题名是什么？
            self.image_callback,  # 收到图后，交给哪个函数处理？(提示：是下面定义的那个函数)
            10  # QoS (队列长度)
        )

        # 6. 创建发布者 (Publisher)
        self.publisher = self.create_publisher(
            DetectionArray,
            '/brain/detections',
            10
        )

        self.get_logger().info("Perception node initialized successfully! Waiting for image message...")


    def load_rt_detr_model(self):
        self.get_logger().info("Loading vision model weights...")

        # 1. 获取文件名参数 (Elegance: 文件名不写死在代码里)
        weights_name = self.get_parameter('weights_file').value
        config_name = self.get_parameter('config_file').value
        # 自动拼接出权重文件的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        checkpoint_path = os.path.join(current_dir, "weights", str(weights_name))
        model_config_path = os.path.join(current_dir, "external_models", "RT_DETR_V2", "configs", "rtdetrv2", str(config_name))

        if not os.path.exists(checkpoint_path):
            self.get_logger().error(f"Cannot found checkpoint in  {checkpoint_path}")
            raise FileNotFoundError(f"Checkpoint missing:  {checkpoint_path}")
        if not os.path.isfile(model_config_path):
            self.get_logger().error(f"Cannot found checkpoint in  {checkpoint_path}")
            raise FileNotFoundError(f"Config file missing: {model_config_path}")

        try:
            conf = YAMLConfig(model_config_path, resume=None)
            model = conf.model.to(self.device)
            model.eval()
        except Exception as model_build_err:
            self.get_logger().error(f"❌ Cannot build rt-detr model: {model_build_err}")
            raise model_build_err

        # --- 2. 加载权重 ---
        self.get_logger().info(f"Loading checkpoint from {checkpoint_path}...")
        try:
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

            load_res = model.load_state_dict(new_state_dict, strict=False)
            # 只有当 missing_keys 很多时才警告，否则只打印 info
            if len(load_res.missing_keys) > 0:
                self.get_logger().warn(
                    f"Weights loaded with {len(load_res.missing_keys)} missing keys (Expected if using a different backbone)")
            else:
                self.get_logger().info("Weights loaded perfectly.")

        except Exception as model_err:
            self.get_logger().error(f"❌ Error loading state_dict: {model_err}")
            raise model_err


        return model

    def image_callback(self, msg):
        """
        brief: 回调函数，每次收到一张图就会被调用一次
        param: msg ROS 发过来的原始图像数据
        """
        try:
            # 将 ROS 图像消息转换为 OpenCV 图像
            # 语法: self.bridge.imgmsg_to_cv2(消息对象, 目标编码)
            # 目标编码通常用 "bgr8" (蓝绿红 8位，这是 OpenCV 的标准格式)
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")

            # # (测试用) 在屏幕上显示图像
            # cv2.imshow("Robot Camera View", cv_image)
            # cv2.waitKey(1)  # 刷新窗口，必须有这句，否则窗口会卡死

        except Exception as cv_err:
            self.get_logger().error(f"Error converting image: {cv_err}")
            raise cv_err

        # 2. 图像预处理 (Pre-processing)
        # 获取原始尺寸 (NumPy shape 是 H, W, C)
        h, w = cv_image.shape[:2]

        # OpenCV (BGR) -> PIL (RGB)
        # 这是为了适配 PyTorch 的标准 Transform，同时也修复了颜色空间问题
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb_image)

        input_tensor = self.transforms(pil_img).unsqueeze(0).to(self.device)

        # 3. 推理
        with torch.no_grad():
            output = self.rt_detr_model(input_tensor)

        # 4. 后处理
        scores = output['pred_logits'].sigmoid()
        boxes = output['pred_boxes']
        # 取第一张图结果
        scores = scores[0]
        boxes = boxes[0]
        # 获取每个框的最大类别分数
        max_scores, class_ids = scores.max(dim=1)
        keep = max_scores > float(self.conf_threshold)
        self.get_logger().info(f"Found {keep.sum()} objects (Threshold: {self.conf_threshold:.2f})")

        # keep.nonzero() 返回所有 True 的索引
        valid_indices = keep.nonzero(as_tuple=True)[0]

        # 5. 发送消息
        detection_array_msg = DetectionArray()
        detection_array_msg.header = msg.header
        if len(valid_indices) > 0:
            # 提取出所有有效的数据
            valid_scores = max_scores[valid_indices]
            valid_classes = class_ids[valid_indices]
            valid_boxes = boxes[valid_indices]

            for i in range(len(valid_indices)):
                box = valid_boxes[i].cpu().numpy()  # [cx, cy, w, h] (0-1)
                score = valid_scores[i].item()
                class_id = valid_classes[i].item()

                # 还原坐标
                cx, cy, bw, bh = box
                cx, cy, bw, bh = cx * w, cy * h, bw * w, bh * h

                # 安全检查：防止 class_id 超出我们定义的列表范围
                if class_id < len(self.classes):
                    label = self.classes[class_id]
                else:
                    label = "unknown"

                # 整合Detection消息
                detection_msg = Detection()
                detection_msg.score = float(score)
                detection_msg.class_id = int(class_id)
                detection_msg.class_name = str(label)
                detection_msg.x_center = float(cx)
                detection_msg.y_center = float(cy)
                detection_msg.width = float(bw)
                detection_msg.height = float(bh)

                # 打包Detection

                detection_array_msg.detections.append(detection_msg)

        # 发送消息
        if len(detection_array_msg.detections) > 0:
            self.publisher.publish(detection_array_msg)
            self.get_logger().info(f"Published {len(detection_array_msg.detections)} objects.")


def main(args=None):
    rclpy.init(args=args)
    node = PerceptionNode()

    try:
        rclpy.spin(node)  # 让节点一直转圈，保持监听状态
    except KeyboardInterrupt:
        pass
    except Exception as unknown_err:
        node.get_logger().error(f"Unknown exception: {unknown_err}")
    finally:
        # 销毁节点，释放资源
        cv2.destroyAllWindows()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()
        print("\n\033[92m[Perception Node] [Info] Exited Cleanly.\033[0m")  # 绿色字体提示


if __name__ == '__main__':
    main()