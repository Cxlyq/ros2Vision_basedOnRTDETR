#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import numpy as np

# 导入 ROS 2 标准消息与自定义语义消息
from geometry_msgs.msg import PoseStamped
from ai_msgs.msg import SemanticVoxelArray, TargetEmbedding


class DtMatcherNode(Node):
    def __init__(self):
        super().__init__('dt_matcher_node')

        # 1. 声明并读取 YAML 参数
        self.declare_parameter('sub_voxel_topic', "/dveformer/semantic_voxels")
        self.declare_parameter('sub_aim_encode_topic', "/dveformer/aim_encode")
        self.declare_parameter('pub_goal_topic', "/goal_pose")
        self.declare_parameter('voxel_size', 0.1)
        self.declare_parameter('update_strategy', "fuse")
        self.declare_parameter('new_voxel_weight', 0.8)
        self.declare_parameter('old_voxel_weight', 0.2)

        self.voxel_size = self.get_parameter('voxel_size').value
        self.strategy = self.get_parameter('update_strategy').value
        self.alpha_new = self.get_parameter('new_voxel_weight').value
        self.alpha_old = self.get_parameter('old_voxel_weight').value

        # 参数强校验
        if self.strategy not in ["replace", "extend", "fuse"]:
            self.get_logger().error(f"[!] Unknown strategy: '{self.strategy}', Using 'fuse' instead.")
            self.strategy = "fuse"

        # 2. 维护全局体素地图的哈希表 (Python dict 能够实现 O(1) 的极速查找)
        # Key: (x_idx, y_idx, z_idx) 的 Tuple
        # Value: numpy array [768] 的归一化特征
        self.global_voxel_map = {}

        # 3. 创建发布者：用于向 Nav2 发送目标点
        self.pub_goal = self.create_publisher(
            PoseStamped,
            self.get_parameter('pub_goal_topic').value,
            10
        )

        # 4. 创建订阅者
        # 订阅局部体素信息
        self.sub_voxels = self.create_subscription(
            SemanticVoxelArray,
            self.get_parameter('sub_voxel_topic').value,
            self.voxel_callback,
            10
        )
        # 订阅目标语义编码
        self.sub_aim_encode = self.create_subscription(
            TargetEmbedding,
            self.get_parameter('sub_aim_encode_topic').value,
            self.aim_encode_callback,
            10
        )

        self.get_logger().info(
            f"[*] Node initialization successful! Now strategy for voxel updating is [{self.strategy}]"
        )

    def voxel_callback(self, msg: SemanticVoxelArray):
        """
        处理前端发来的每一帧局部体素，并根据指定策略更新到全局地图中
        """
        new_count = 0
        updated_count = 0
        ignored_count = 0

        for voxel in msg.voxels:
            voxel_key = (voxel.x_index, voxel.y_index, voxel.z_index)
            incoming_feature = np.array(voxel.feature, dtype=np.float32)

            # 情况 A：全新空间索引，直接保存
            if voxel_key not in self.global_voxel_map:
                self.global_voxel_map[voxel_key] = incoming_feature
                new_count += 1
                continue

            # 情况 B：索引重复，触发策略选择
            if self.strategy == "replace":
                # 策略1：完全更新，保留新数据
                self.global_voxel_map[voxel_key] = incoming_feature
                updated_count += 1

            elif self.strategy == "extend":
                # 策略2：仅扩展，保留旧数据，丢弃新数据
                ignored_count += 1
                pass

            elif self.strategy == "fuse":
                # 策略3：融合扩展，加权融合后重新进行 L2 归一化
                old_feature = self.global_voxel_map[voxel_key]
                fused_feature = self.alpha_new * incoming_feature + self.alpha_old * old_feature

                # 重新进行 L2 归一化以保证相似度计算的准确性
                norm = np.linalg.norm(fused_feature)
                if norm > 1e-8:
                    fused_feature /= norm

                self.global_voxel_map[voxel_key] = fused_feature
                updated_count += 1

        self.get_logger().info(
            f"[*] Map updated. New come: {new_count}, Update: {updated_count}, Ignore: {ignored_count}. "
            f"[*] Global voxel quantity: {len(self.global_voxel_map)}"
        )

    def aim_encode_callback(self, msg: TargetEmbedding):
        """
        收到目标语义特征后，遍历地图计算相似度，寻找最佳匹配体素并解算坐标送给 Nav2
        """
        if not self.global_voxel_map:
            self.get_logger().warn("[?] Global voxel list is EMPTY! Cannot calculate target position.")
            return

        target_word = msg.target_word
        # 转换为 numpy 向量 [768]
        target_embedding = np.array(msg.embedding, dtype=np.float32)

        self.get_logger().info(f"[*] Searching for: '{target_word}'...")

        best_key = None
        best_similarity = -1.0

        # 遍历字典进行特征点积（因为两边都经过了 L2 归一化，点积即为余弦相似度）
        for voxel_key, voxel_feature in self.global_voxel_map.items():
            similarity = float(np.dot(target_embedding, voxel_feature))

            if similarity > best_similarity:
                best_similarity = similarity
                best_key = voxel_key

        # 输出匹配结果
        self.get_logger().info(f"[*] Searching finish: {best_similarity:.4f}")

        # 设置一个基础阈值，防止在完全不包含该物体的环境中乱导航
        if best_similarity < 0.1:
            self.get_logger().warn(
                f"[?] Cannot found '{target_word}' (whit highest match rate is {best_similarity:.4f})")
            return

        # 5. 根据最佳体素网格索引解算 /map 坐标系下的物理中心坐标
        # best_key 结构为 (x_index, y_index, z_index)
        map_x = (best_key[0] + 0.5) * self.voxel_size
        map_y = (best_key[1] + 0.5) * self.voxel_size
        map_z = (best_key[2] + 0.5) * self.voxel_size

        self.get_logger().info(
            f"[*] Target '{target_word}' located！"
            f"[*] Voxel index {best_key}, Global position: X={map_x:.2f}m, Y={map_y:.2f}m, Z={map_z:.2f}m"
        )

        # 6. 组装并发布 Nav2 目标点消息
        goal_msg = PoseStamped()
        # 使用标准的 'map' 坐标系
        goal_msg.header.frame_id = "map"
        goal_msg.header.stamp = self.get_clock().now().to_msg()

        # 2D 导航仅需指定 X 和 Y 坐标
        goal_msg.pose.position.x = map_x
        goal_msg.pose.position.y = map_y
        goal_msg.pose.position.z = 0.0  # 2D 导航通常将高度设为地面 0.0

        # 默认朝向（四元数，此处设为不旋转，即面向 X 轴正方向）
        goal_msg.pose.orientation.w = 1.0
        goal_msg.pose.orientation.x = 0.0
        goal_msg.pose.orientation.y = 0.0
        goal_msg.pose.orientation.z = 0.0

        # 广播给 Nav2 导航堆栈
        self.pub_goal.publish(goal_msg)
        self.get_logger().info(f"[*] Publish pose to Nav2 successfully！")


def main(args=None):
    rclpy.init(args=args)
    node = DtMatcherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("[*] DT Matcher Node Shutting down...")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()