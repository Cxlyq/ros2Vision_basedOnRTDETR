import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
import math

# 导入消息类型
from ai_msgs.msg import DetectionArray, ObstacleInfo, ObstacleArray
from geometry_msgs.msg import Point
from .obstacle_tracker import ObstacleTracker

# TF2 库
from tf2_ros import Buffer, TransformListener
from tf2_ros import LookupException, ConnectivityException, ExtrapolationException
# 用于将 ROS 的 TF 消息转换为数学计算用的矩阵
from tf2_geometry_msgs import do_transform_point



class EstimationNode(Node):
    def __init__(self):
        super().__init__('estimation_node')

        # --- 声明并读取参数 ---
        # 与 yaml 文件里的对应
        self.declare_parameter('camera_fx', 1.0)
        self.declare_parameter('camera_fy', 1.0)
        self.declare_parameter('camera_cx', 320.0)
        self.declare_parameter('camera_cy', 240.0)
        self.declare_parameter('camera_height', 0.1)
        self.declare_parameter('camera_tilt', 0.0)

        self.declare_parameter('match_distance_threshold', 0.5)
        self.declare_parameter('smooth_param', 0.8)
        self.declare_parameter('missed_frames', 10)

        # 读取参数值到变量中
        self.fx = self.get_parameter('camera_fx').value
        self.fy = self.get_parameter('camera_fy').value
        self.cx = self.get_parameter('camera_cx').value
        self.cy = self.get_parameter('camera_cy').value
        self.cam_h = self.get_parameter('camera_height').value
        self.cam_tilt = self.get_parameter('camera_tilt').value
        self.match_distance_threshold = self.get_parameter('match_distance_threshold').value
        self.smooth_param = self.get_parameter('smooth_param').value
        self.missed_frames = self.get_parameter('missed_frames').value

        self.get_logger().info(f"Parameters loaded: Cam_height={self.cam_h}m, fx={self.fx}")

        # --- 初始化 TF 监听器 ---
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # --- 初始化记忆列表 ---
        self.obstacles_long_term_memory : list[ObstacleTracker] = []
        self.obstacles_temp_term_memory : list[ObstacleTracker] = []
        self.frame_count = 0
        self.o_id_counter = 0

        # --- 创建订阅者 ---
        # 订阅 RT-DETR 发出的检测框
        self.subscription = self.create_subscription(
            DetectionArray,
            '/brain/detections',
            self.detection_callback,
            10
        )

        # --- 创建发布者 ---
        # 发布障碍物位置信息列表
        self.publisher = self.create_publisher(
            ObstacleArray,
            '/brain/obstacles',
            10
        )
        self.get_logger().info("Estimation node initialized successfully! Waiting for detection message...")

    def calculate_position_from_pixels(self, u, v):
        """
        利用地面约束法计算物体相对于相机的距离
        u, v: 像素坐标 (物体底边中心点)
        return: (distance_forward, distance_lateral) 单位米
        """
        # 1. 计算垂直视场角 alpha (相对于光心)
        # 注意 v 越大，物体越靠下 (Y轴向下)
        alpha = math.atan((v - self.cy) / self.fy)

        # 2. 计算地面投影距离 (Distance Forward)
        # 公式: D = H / tan(tilt + alpha)
        # 注意: 这里的角度方向可能需要根据实际坐标系微调正负号
        # 假设 tilt=0, alpha > 0 (物体在地平线以下), 则 tan > 0, dist > 0
        ground_angle = self.cam_tilt + alpha

        if ground_angle <= 0:
            # 这种情况意味着物体在地平线以上(飞在天上?) 或者 计算出错
            return None, None

        distance = self.cam_h / math.tan(ground_angle)

        # 3. 计算横向偏移 (Lateral)
        # 利用水平相似三角形
        beta = math.atan((u - self.cx) / self.fx)
        lateral = distance * math.tan(beta)

        return distance, lateral

    def detection_callback(self, msg):

        self.frame_count += 1

        # 1. 获取当前时刻 机器人(base_link) -> 世界(odom) 的变换关系
        detection_time = msg.header.stamp
        try:
            # 查表：找 "odom" 到 "base_link" 的变换
            # 注意time统一，使用detectionArray.msg header 时间戳
            transform = self.tf_buffer.lookup_transform(
                'odom',  # 目标坐标系 (Target)
                'base_link',  # 源坐标系 (Source) - 或者直接用 camera_link
                detection_time,
                rclpy.duration.Duration(seconds=0.1)  # 超时容忍
            )
        except (LookupException, ConnectivityException, ExtrapolationException) as tf_e:
            self.get_logger().warn(f'Failed to look up TF: {tf_e}')
            return

        # 2. 处理每一个检测到的物体
        if len(msg.detections) > 0:
            for detection in msg.detections:
                # 提取物品信息
                obstacle_id = detection.class_id
                obstacle_label = detection.class_name
                # 提取识别置信度
                score = detection.score
                # 提取框的底部中心点
                u = detection.bbox.x
                v = detection.bbox.y + detection.bbox.h / 2.0

                # A. 算出相对距离 (相对于相机)
                dist, lat = self.calculate_position_from_pixels(u, v)
                if dist is None:
                    continue

                # B. 构造一个局部坐标点 (在 base_link 坐标系下)
                # 假设相机装在车头，且相机坐标系 x向前, y向左
                # 这里算出的 dist 是前方距离(ROS X轴), lat 是左方距离(ROS Y轴, 注意正负)
                p_local = Point()
                p_local.x = float(dist)
                p_local.y = float(-lat)  # 图像右边是正，但在ROS坐标系右边是Y的负方向
                p_local.z = 0.0

                # C. 核心：坐标变换 (Local -> Global)
                # 使用 do_transform_point 将点转换到 odom 坐标系
                from geometry_msgs.msg import PointStamped
                p_stamped = PointStamped()
                p_stamped.header.frame_id = "base_link"
                p_stamped.header.stamp = detection_time
                p_stamped.point = p_local
                try:
                    # 这一步把“车前的点”变成了“房间里的点”
                    p_global = do_transform_point(p_stamped, transform)

                    self.get_logger().info(
                        f"Object [{detection.class_id}] - 相对距离: {dist:.2f}m - "
                        f"绝对坐标: ({p_global.point.x:.2f}, {p_global.point.y:.2f})"
                    )
                    # 建立tracker，存入临时记忆
                    obstacle = ObstacleTracker(obstacle_id, obstacle_label, score, p_global, dist, lat, self.frame_count)
                    self.obstacles_temp_term_memory.append(obstacle)
                except Exception as coordinate_e:
                    self.get_logger().warn(f"Failed to transform coordinate: {coordinate_e}")

            # 3. update memory
            self.update_memory()

            # 4. send message
            if len(self.obstacles_long_term_memory) > 0:
                obstacle_array_msg = self.mem2msg()
                self.publisher.publish(obstacle_array_msg)


    def update_memory(self):
        current_time = self.frame_count

        # 1. 匹配过程
        for new_obs in self.obstacles_temp_term_memory:
            best_match = None
            min_dist = float('inf')

            # 在长期记忆里找最近的
            for known_obs in self.obstacles_long_term_memory:
                dist = math.sqrt((new_obs.obstacle_position_glob.point.x - known_obs.obstacle_position_glob.point.x) ** 2 + (new_obs.obstacle_position_glob.point.y - known_obs.obstacle_position_glob.point.y) ** 2)

                # 只有距离够近，且类别相同，才认为是同一个
                if dist < min_dist and dist < self.match_distance_threshold and new_obs.obstacle_label == known_obs.obstacle_label:
                    min_dist = dist
                    best_match = known_obs

            if best_match:
                # 找到了：更新位置 (可以使用加权平均来平滑抖动)
                # 简单的移动平均: 新位置 = 旧位置 * 0.8 + 新位置 * 0.2
                best_match.obstacle_position_glob.point.x = new_obs.obstacle_position_glob.point.x * (1-self.smooth_param) + best_match.obstacle_position_glob.point.x * self.smooth_param
                best_match.obstacle_position_glob.point.y = new_obs.obstacle_position_glob.point.y * (1-self.smooth_param) + best_match.obstacle_position_glob.point.y * self.smooth_param
                best_match.missed_frames = 0
                best_match.last_seen = self.frame_count
            else:
                # 没找到：这是个新障碍物
                # 新障碍物添加到长期记忆时，为其分配唯一的id
                new_obs.obstacle_id = self.o_id_counter
                self.o_id_counter += 1
                self.obstacles_long_term_memory.append(new_obs)



        # 2. 清理过程 (遗忘)
        # 倒序遍历以便安全删除
        for i in range(len(self.obstacles_long_term_memory) - 1, -1, -1):
            obs = self.obstacles_long_term_memory[i]

            # 如果这一帧没更新，missed_frames + 1
            if obs.last_seen != current_time:
                obs.missed_frames += 1

            # 移除条件：
            # 连续 10 帧没看到
            if obs.missed_frames > self.missed_frames:
                self.obstacles_long_term_memory.pop(i)

        # 清空短期记忆，为下一帧做准备
        self.obstacles_temp_term_memory.clear()


    def mem2msg(self):
        obstacle_array_msg = ObstacleArray()
        for obstacle in self.obstacles_long_term_memory:
            obstacle_info_msg = ObstacleInfo()
            obstacle_info_msg.id = obstacle.obstacle_id
            obstacle_info_msg.label = obstacle.obstacle_label
            obstacle_info_msg.score = obstacle.obstacle_score
            obstacle_info_msg.position_odom = obstacle.obstacle_position_glob
            obstacle_info_msg.distance = obstacle.obstacle_distance
            obstacle_info_msg.lateral = obstacle.obstacle_lateral
            obstacle_array_msg.obstacles.append(obstacle_info_msg)
        return obstacle_array_msg

def main(args=None):
    rclpy.init(args=args)
    node = EstimationNode()

    try:
        rclpy.spin(node)  # 让节点一直转圈，保持监听状态
    except KeyboardInterrupt:
        pass
    except Exception as unknown_err:
        node.get_logger().error(f"Unknown exception: {unknown_err}")
    finally:
        # 销毁节点，释放资源
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print("\n\033[92m[Estimation Node] [Info] Exited Cleanly.\033[0m")  # 绿色字体提示


if __name__ == '__main__':
    main()