import os
import sys
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from cv_bridge import CvBridge
import numpy as np
import cv2
import torch
import torch.nn.functional as F

# 让 Python 能够找到 external_models 下的包
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'external_models'))
from nicr_mt_scene_analysis.data import move_batch_to_device
from nicr_mt_scene_analysis.data import mt_collate
from external_models.DVEFormer.dveformer.args import ArgParserDVEFormer
from external_models.DVEFormer.dveformer.model import DVEFormer
from external_models.DVEFormer.dveformer.weights import load_weights
from external_models.DVEFormer.dveformer.preprocessing import get_preprocessor
import alpha_clip

# messages
from sensor_msgs.msg import Image, CameraInfo
from ai_msgs.msg import TargetEmbedding, SemanticVoxel, SemanticVoxelArray
from std_msgs.msg import String
import message_filters

from scipy.spatial.transform import Rotation as R # 用于处理四元数到旋转矩阵的转换
from tf2_ros import Buffer, TransformListener
from tf2_ros import LookupException, ConnectivityException, ExtrapolationException

# ==========================================
# 伪造数据集配置 (Mocking Configuration)
# ==========================================
class MockDepthStats:
    mean = 2.8424
    std = 0.9722


class MockSemanticLabelList(list):
    @property
    def classes_is_thing(self):
        return (False,) * 40

    @property
    def classes_use_orientations(self):
        return (False,) * 40


class MockConfig:
    depth_stats = MockDepthStats()
    semantic_label_list_without_void = MockSemanticLabelList([None] * 40)
    semantic_label_list = MockSemanticLabelList([None] * 41)
    scene_label_list_without_void = [None] * 10


class MockDataset:
    config = MockConfig()
    sample_keys = ('rgb', 'depth', 'identifier')
    camera = 'default'


class DVEFormerNode(Node):
    def __init__(self):
        super().__init__('dveformer_node')

        # 1. 声明并读取所有参数
        self.declare_parameters(
            namespace='',
            parameters=[
                ('dveformer_weights_path', rclpy.Parameter.Type.STRING),
                ('alpha_clip_ckpt_path', rclpy.Parameter.Type.STRING),
                ('alpha_clip_model_name', "ViT-L/14@336px"),
                ('device', 'cuda:0'),
                ('inference_input_width', 640),
                ('inference_input_height', 480),
                ('depth_scale', 1.0),
                ('depth_max', 10.0),
                ('prompt_template', "a photo of a {}"),
                ('similarity_threshold', 0.25),
                ('sub_rgb_topic', "/camera/color/image_raw"),
                ('sub_depth_topic', "/camera/depth/image_raw"),
                ('sub_aim_topic', "/user_inst/aim_obj"),
                ('sub_camera_info_topic', "/camera/depth/camera_info"),
                ('pub_aim_encode_topic', "/dveformer/aim_encode"),
                ('pub_voxel_topic', "/dveformer/semantic_voxels"),
                ('voxel_size', 0.1),
                ('map_frame_id', "map"),
            ]
        )

        # 提取参数到实例变量
        self.device = self.get_parameter('device').value
        self.depth_scale = self.get_parameter('depth_scale').value
        self.depth_max = self.get_parameter('depth_max').value
        self.prompt_template = self.get_parameter('prompt_template').value
        self.threshold = self.get_parameter('similarity_threshold').value

        dveformer_ckpt = self.get_parameter('dveformer_weights_path').value
        clip_ckpt = self.get_parameter('alpha_clip_ckpt_path').value
        clip_model_name = self.get_parameter('alpha_clip_model_name').value
        self.voxel_size = self.get_parameter('voxel_size').value
        self.map_frame_id = self.get_parameter('map_frame_id').value
        self.fx = None
        self.fy = None
        self.cx = None
        self.cy = None
        self._intrinsics_initialized = False  # 用于防止日志刷屏的标志位

        self.get_logger().info("[Init] Loading Models... This may take a while.")

        # 2. 初始化 DVEFormer 模型
        self.model, self.preprocessor = self._init_dveformer(dveformer_ckpt)

        # 3. 初始化 Alpha-CLIP 文本编码器
        self.clip_model = self._init_alpha_clip(clip_model_name, clip_ckpt)

        # 4. 状态变量
        self.cv_bridge = CvBridge()
        self.current_target_string = None
        self.current_text_embeddings = None

        # 5. 初始化 TF2 监听器
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # 6. 建立 ROS 2 话题发布者 (Publisher)
        # pub_aim_encode 发布语义字符串编码信息
        self.pub_aim_encode = self.create_publisher(
            TargetEmbedding,
            self.get_parameter('pub_aim_encode_topic').value,
            10
        )
        # pub_voxel_topic 建立体素发布者
        self.pub_voxel = self.create_publisher(
            SemanticVoxelArray,
            self.get_parameter('pub_voxel_topic').value,
            10
        )

        # 7. 建立 ROS 2 话题订阅者 (Subscriber)
        # 订阅 CameraInfo 话题
        self.sub_camera_info = self.create_subscription(
            CameraInfo,
            self.get_parameter('sub_camera_info_topic').value,
            self.camera_info_callback,
            10
        )
        # 文本指令订阅：触发文本特征更新
        self.sub_aim = self.create_subscription(
            String,
            self.get_parameter('sub_aim_topic').value,
            self.aim_callback,
            10
        )
        # RGBD 时间戳对齐订阅 (使用 ApproximateTimeSynchronizer 容忍微小的时间偏差)
        self.sub_rgb = message_filters.Subscriber(self, Image, self.get_parameter('sub_rgb_topic').value)
        self.sub_depth = message_filters.Subscriber(self, Image, self.get_parameter('sub_depth_topic').value)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.sub_rgb, self.sub_depth],
            queue_size=10,
            slop=0.1  # 允许 0.1 秒的时间戳误差
        )
        self.ts.registerCallback(self.rgbd_callback)

        self.get_logger().info("[Init] DVEFormer Node has been successfully started!")

    def _init_dveformer(self, weights_path):
        parser = ArgParserDVEFormer()
        args = parser.parse_args([])

        args.validation_input_height = self.get_parameter('inference_input_height').value
        args.validation_input_width = self.get_parameter('inference_input_width').value
        args.device = self.device
        args.weights_filepath = weights_path
        args.enable_linear_probing = False
        args.no_pretrained_backbone = True
        args.dataset = 'nyuv2'
        args.input_modalities = 'rgbd'
        args.scale_depth = False
        args.raw_depth = False
        args.tasks = ('dense-visual-embedding',)
        args.enable_panoptic = False

        dataset_config = MockConfig()
        model = DVEFormer(args, dataset_config=dataset_config)

        checkpoint = torch.load(weights_path, map_location='cpu')
        state_dict = checkpoint['state_dict'] if 'state_dict' in checkpoint else checkpoint
        load_weights(args, model, state_dict, verbose=False)

        model = model.to(self.device)
        model.eval()

        mock_dataset = MockDataset()
        preprocessor = get_preprocessor(args, dataset=mock_dataset, phase='test', multiscale_downscales=None)
        return model, preprocessor

    def _init_alpha_clip(self, model_name, ckpt_path):
        model, _ = alpha_clip.load(model_name, alpha_vision_ckpt_pth=ckpt_path, device=self.device)
        model.eval()
        return model

    def process_and_publish_voxels(self, dense_features, img_depth, header):
        """
        将 2D 特征图与深度图结合，投影至全局 3D 空间，进行体素化和局部池化，最终发布。
        """
        # 确保调用该函数时相机内参已加载成功
        if self.fx is None:
            # warn_once 只报一次警
            self.get_logger().warn_once("[Mapping] Waiting for CameraInfo to initialize intrinsics...")
            return

        camera_frame_id = header.frame_id
        if "optical" not in camera_frame_id.lower():
            self.get_logger().warn_once(
                f"[Warning] header.frame_id is '{camera_frame_id}', except camera_depth_optional_frame!"
            )
        # 1. 获取 Camera 到 Map 的 TF 变换
        try:
            # 允许 0.1 秒的等待时间，获取图像时间戳时刻的位姿
            t = self.tf_buffer.lookup_transform(
                self.map_frame_id,
                camera_frame_id,
                header.stamp,
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().debug(f"[Error] TF 变换获取失败: {e}")
            return

        # 构造 4x4 变换矩阵 (T_map_cam)
        trans = [t.transform.translation.x, t.transform.translation.y, t.transform.translation.z]
        quat = [t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z, t.transform.rotation.w]
        rot_mat = R.from_quat(quat).as_matrix()

        T_map_cam = np.eye(4)
        T_map_cam[:3, :3] = rot_mat
        T_map_cam[:3, 3] = trans

        # 2. 向量化反投影 (2D -> 3D Camera Frame)
        H, W = img_depth.shape
        v, u = np.indices((H, W))  # v对应高(Y), u对应宽(X)

        # 筛选有效深度 (大于0且小于深度阈值)
        valid_mask = (img_depth > 0) & (img_depth < self.depth_max)

        z = img_depth[valid_mask]
        if z.shape[0] == 0:
            self.get_logger().warn(f"[?] Current depth frame has no valid data.")
            return
        u_valid = u[valid_mask]
        v_valid = v[valid_mask]

        # 根据相机内参计算 3D 坐标
        x = (u_valid - self.cx) * z / self.fx
        y = (v_valid - self.cy) * z / self.fy

        points_cam = np.stack((x, y, z), axis=-1)  # shape: [N, 3]

        # 提取有效像素对应的 768 维特征
        # dense_features 原本是 [1, 768, H, W]，转换为 [H, W, 768]
        feat_map = dense_features.squeeze(0).permute(1, 2, 0).cpu().numpy()
        features_flat = feat_map[valid_mask]  # shape: [N, 768]

        # 3. 坐标转换至 Map 系
        N = points_cam.shape[0]
        points_cam_homo = np.hstack((points_cam, np.ones((N, 1))))  # [N, 4]
        points_map_homo = (T_map_cam @ points_cam_homo.T).T  # [N, 4]
        points_map = points_map_homo[:, :3]  # [N, 3]

        # 4. 计算体素索引
        voxel_indices = np.floor(points_map / self.voxel_size).astype(np.int32)

        # 5. 体素化去重与特征均值池化 (Mean Pooling)
        # np.unique 返回唯一的体素坐标，以及原始坐标在唯一坐标数组中的索引
        unique_voxels, inverse_indices = np.unique(voxel_indices, axis=0, return_inverse=True)

        num_unique_voxels = len(unique_voxels)
        sum_features = np.zeros((num_unique_voxels, 768), dtype=np.float32)
        counts = np.zeros((num_unique_voxels, 1), dtype=np.float32)

        # 利用 numpy.add.at 进行极速聚合累加
        np.add.at(sum_features, inverse_indices, features_flat)
        np.add.at(counts, inverse_indices, 1)

        # 求平均
        mean_features = sum_features / counts

        # 6. L2 归一化
        norms = np.linalg.norm(mean_features, axis=1, keepdims=True)
        # 加上 1e-8 防止除以 0
        normalized_features = mean_features / (norms + 1e-8)

        # 7. 组装并发布 SemanticVoxelArray 消息
        voxel_array_msg = SemanticVoxelArray()
        voxel_array_msg.header = header
        voxel_array_msg.header.frame_id = self.map_frame_id
        voxel_array_msg.voxel_size = self.voxel_size

        for i, idx in enumerate(unique_voxels):
            vox_msg = SemanticVoxel()
            vox_msg.x_index = int(idx[0])
            vox_msg.y_index = int(idx[1])
            vox_msg.z_index = int(idx[2])
            vox_msg.feature = normalized_features[i].tolist()

            voxel_array_msg.voxels.append(vox_msg)

        self.pub_voxel.publish(voxel_array_msg)
        self.get_logger().info(f"[Mapping] Published {num_unique_voxels} semantic voxels to map.")

    def extract_image_features(self, img_rgb, img_depth, identifier):
        """修改自原脚本，现在直接接收 numpy 数组而非文件路径"""
        sample = self.preprocessor({
            'rgb': img_rgb,
            'depth': img_depth,
            'identifier': identifier
        })

        batch = mt_collate([sample])
        batch = move_batch_to_device(batch, device=torch.device(self.device))

        with torch.no_grad():
            with torch.autocast(device_type=self.device.split(':')[0], dtype=torch.float16):
                predictions = self.model(batch, do_postprocessing=True)

        embedding_key = 'dense_visual_embedding_output'
        if embedding_key in predictions:
            return predictions[embedding_key]
        else:
            return list(predictions.values())[0]

    def camera_info_callback(self, msg: CameraInfo):
        """
        动态获取相机内参。
        ROS 2 CameraInfo.K 是一个展平的 1D 数组，长度为 9:
        [fx,  0, cx]
        [ 0, fy, cy]
        [ 0,  0,  1]
        """
        self.fx = msg.k[0]
        self.cx = msg.k[2]
        self.fy = msg.k[4]
        self.cy = msg.k[5]

        # 仅在第一次获取到内参时打印日志
        if not self._intrinsics_initialized:
            self.get_logger().info(
                f"[Camera] Intrinsics successfully initialized from topic: "
                f"fx={self.fx:.2f}, fy={self.fy:.2f}, cx={self.cx:.2f}, cy={self.cy:.2f}"
            )
            self._intrinsics_initialized = True

    def aim_callback(self, msg: String):
        """
        接收到新的目标字符串时：
        1. 使用 Alpha-CLIP 计算文本特征
        2. 缓存该特征
        3. 封装为 TargetEmbedding 消息直接向后端（或其他节点）发布
        """
        target_str = msg.data.strip()
        if target_str == self.current_target_string:
            return # 目标没变，不需要重复提取

        self.current_target_string = target_str
        self.get_logger().info(f"[Aim] Received new target: '{target_str}'")

        # 1. Prompt 工程与 Tokenize
        formatted_prompt = self.prompt_template.format(target_str)
        tokens = alpha_clip.tokenize([formatted_prompt]).to(self.device)

        with torch.no_grad():
            # 2. 提取特征并做 L2 归一化
            text_features = self.clip_model.encode_text(tokens)
            self.current_text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

        self.get_logger().info("[Aim] Text embedding calculated successfully.")

        # 3. 组装 ROS 2 消息并发布
        embed_msg = TargetEmbedding()
        embed_msg.target_word = target_str

        # 将 PyTorch Tensor [1, 768] 转换为 1D numpy array，再转为 Python 列表
        # ROS 2 的 float32[] 接口接收原生的 Python list
        embedding_list = self.current_text_embeddings.squeeze().cpu().numpy().tolist()
        embed_msg.embedding = embedding_list

        self.pub_aim_encode.publish(embed_msg)
        self.get_logger().info(f"[Aim] Published 768-dim embedding for '{target_str}' to back-end.")

    def rgbd_callback(self, rgb_msg: Image, depth_msg: Image):
        """
        核心回调：每帧触发，进行特征提取与跨模态匹配
        """
        # 1. 强校验并转换为 numpy
        try:
            # 强制转为 RGB 3通道
            img_rgb = self.cv_bridge.imgmsg_to_cv2(rgb_msg, desired_encoding='rgb8')
            # 使用 passthrough 接收深度，通常是 16UC1 毫米级 或 32FC1 米级
            img_depth_raw = self.cv_bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
        except Exception as e:
            self.get_logger().error(f"[Error] cv_bridge conversion failed: {e}")
            return

        # 确保深度图是 float32 单通道
        img_depth = img_depth_raw.astype(np.float32)
        if img_depth.ndim == 3:
            img_depth = img_depth[:, :, 0]

        # ==========================================================
        # 新增适配Gemini pro的 RGB-D 异构分辨率对齐逻辑
        # 目标：将 640x400 的深度图安全转换为 640x480，不破坏物理光心
        # ==========================================================
        rgb_h, rgb_w = img_rgb.shape[:2]
        depth_h, depth_w = img_depth.shape[:2]

        if rgb_w == depth_w and rgb_h != depth_h:
            if rgb_h == 480 and depth_h == 400:
                # 计算需要补齐的总高度差 (通常是 80)
                diff_h = rgb_h - depth_h
                top_pad = diff_h // 2  # 顶部补 40 行
                bottom_pad = diff_h - top_pad  # 底部补 40 行

                # 使用 numpy.pad 进行极速 Zero-Padding
                img_depth = np.pad(
                    img_depth,
                    pad_width=((top_pad, bottom_pad), (0, 0)),
                    mode='constant',
                    constant_values=0
                )

                # 同步处理原始数据副本（用于后续的 3D 体素化发布）
                img_depth_raw = np.pad(
                    img_depth_raw,
                    pad_width=((top_pad, bottom_pad), (0, 0)),
                    mode='constant',
                    constant_values=0
                )

                # 日志降级为 debug 防止刷屏，只在需要调试时查看
                self.get_logger().debug("[Align] Auto-padded Depth from 640x400 to 640x480.")
            else:
                self.get_logger().warn(
                    f"[Warn] Unhandled resolution mismatch: RGB {rgb_w}x{rgb_h}, Depth {depth_w}x{depth_h}")
                return
        elif rgb_w != depth_w or rgb_h != depth_h:
            self.get_logger().error("[Error] Critical dimension mismatch requiring complex geometric registration.")
            return
        # ==========================================================



        # 深度数据预处理
        img_depth *= self.depth_scale
        if self.depth_max is not None:
            img_depth[img_depth > self.depth_max] = 0

        # 2. 图像特征提取
        identifier = str(rgb_msg.header.stamp.sec)  # 用时间戳秒作为伪 identifier
        dense_features = self.extract_image_features(img_rgb, img_depth, identifier)

        # 3. 提取特征后，立刻执行 3D 投影和体素化广播
        self.process_and_publish_voxels(dense_features, img_depth_raw.astype(np.float32) * self.depth_scale,
                                        rgb_msg.header)


def main(args=None):
    rclpy.init(args=args)
    node = DVEFormerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard Interrupt, shutting down...")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()