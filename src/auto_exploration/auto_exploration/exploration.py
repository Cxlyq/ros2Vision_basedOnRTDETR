#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

# 消息与服务类型
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseStamped
from std_srvs.srv import Trigger
from nav2_msgs.action import NavigateToPose

# 数学运算库
import numpy as np
import cv2

class ExplorerNode(Node):
    def __init__(self):
        super().__init__('auto_exploration')
        self.get_logger().info("[*] Automatic exploration node has started, waiting for instruction...")

        # ---------------- 1. 声明并获取参数 ----------------
        self.declare_parameter('map_topic', '/map')
        self.declare_parameter('robot_frame', 'base_link')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('loop_rate', 1.0)
        self.declare_parameter('frontier_size_threshold', 15)

        self.map_topic = self.get_parameter('map_topic').value
        self.robot_frame = self.get_parameter('robot_frame').value
        self.global_frame = self.get_parameter('global_frame').value
        self.loop_rate = self.get_parameter('loop_rate').value
        self.frontier_size_threshold = self.get_parameter('frontier_size_threshold').value

        # ---------------- 2. 核心状态标志位 ----------------
        self.is_exploring = False  # 探图总开关
        self.is_navigating = False  # 记录 Nav2 是否正在执行任务
        self.latest_map = None  # 缓存最新地图数据
        self.current_goal_handle = None  # 保存当前发送给 Nav2 的目标句柄

        # ---------------- 3. ROS 2 通信接口定义 ----------------
        # 订阅代价地图
        self.map_sub = self.create_subscription(
            OccupancyGrid,
            self.map_topic,
            self.map_callback,
            10
        )

        # Nav2 动作客户端 (用于发送目标点并监控状态)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # 启动/停止 服务 (Server)
        self.start_srv = self.create_service(Trigger, 'start_exploration', self.start_callback)
        self.stop_srv = self.create_service(Trigger, 'stop_exploration', self.stop_callback)

        # ---------------- 4. 启动主循环定时器 ----------------
        timer_period = 1.0 / self.loop_rate
        self.timer = self.create_timer(timer_period, self.exploration_loop)

    # ==================== 回调函数区 ====================

    def map_callback(self, msg):
        """地图订阅回调，实时更新本地地图缓存"""
        self.latest_map = msg

    def start_callback(self, request, response):
        """处理启动请求"""
        if not self.latest_map:
            response.success = False
            response.message = "Cannot enable because map data is empty"
            self.get_logger().warn(response.message)
            return response

        self.is_exploring = True
        response.success = True
        response.message = "Exploration start!"
        self.get_logger().info(response.message)
        return response

    def stop_callback(self, request, response):
        """处理停止请求"""
        self.is_exploring = False
        if self.is_navigating and self.current_goal_handle is not None:
            self.get_logger().info("[*] Sending stop request to nav2...")
            cancel_future = self.current_goal_handle.cancel_goal_async()
            cancel_future.add_done_callback(self.cancel_done_callback)
        self.is_navigating = False

        response.success = True
        response.message = "Exploration stopped!"
        self.get_logger().info(response.message)
        return response

    def cancel_done_callback(self, future):
        """处理取消目标请求的回调"""
        cancel_response = future.result()

        # 如果 goals_canceling 列表长度大于 0，说明成功取消了任务
        if len(cancel_response.goals_canceling) > 0:
            self.get_logger().info("[*] Navigation has been cancelled successfully.")
        else:
            self.get_logger().warn("[?] Failed to cancel the navigation or navigation has done.")
    # ==================== 核心逻辑区 ====================

    def exploration_loop(self):
        """
        定时器主循环：频率由 loop_rate 决定。
        只在 is_exploring 为 True 且 Nav2 空闲时执行计算。
        """
        # 1. 检查总开关
        if not self.is_exploring:
            return

        # 2. 检查地图是否就绪
        if self.latest_map is None:
            self.get_logger().debug("[-] Waiting for map data...")
            return

        # 3. 检查 Nav2 是否正在忙碌
        if self.is_navigating:
            self.get_logger().debug("[] Nav2 is going to navigation point, gap the request...")
            return

        self.get_logger().info("[*] Start finding unexplored zone...")

        # 1. 地图数据处理
        # 取出地图的基本属性
        map_info = self.latest_map.info
        w, h = map_info.width, map_info.height
        res = map_info.resolution
        ox, oy = map_info.origin.position.x, map_info.origin.position.y

        # 将 1D 元组转换为 NumPy 数组，并重塑为 2D 矩阵 [y, x]
        grid = np.array(self.latest_map.data, dtype=np.int8).reshape((h, w))

        # 2. 边界提取
        # 二值化：提取 Free 空间 (0) 和 Unknown 空间 (-1)
        free_mask = np.where(grid == 0, 255, 0).astype(np.uint8)
        unknown_mask = np.where(grid == -1, 255, 0).astype(np.uint8)
        # 膨胀 Free 空间 (使用 3x3 的十字形核，向外扩张 1 格)
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        free_dilated = cv2.dilate(free_mask, kernel, iterations=1)
        # 逻辑与：膨胀后的 Free 碰到 Unknown 的地方就是边界
        frontier_mask = cv2.bitwise_and(free_dilated, unknown_mask)

        # 3. 寻找与过滤连通域
        # 寻找轮廓 (连通域)
        contours, _ = cv2.findContours(frontier_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        # 过滤噪点
        valid_frontiers = [c for c in contours if len(c) > self.frontier_size_threshold]
        if not valid_frontiers:
            self.get_logger().warn("[?] Did not find any valid frontier.")
            self.is_exploring = False
            return

        # 4. 解算目标点
        largest_frontier = max(valid_frontiers, key=len)
        # 计算这块边界的几何质心
        M = cv2.moments(largest_frontier)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            cx, cy = largest_frontier[0][0][0], largest_frontier[0][0][1]

        # 将像素坐标 (cx, cy) 转换为物理坐标
        target_x = ox + (cx * res)
        target_y = oy + (cy * res)

        self.get_logger().info(f"[*] Find target at: X={target_x:.2f}, Y={target_y:.2f}")
        # 发送目标
        self.send_goal_to_nav2(target_x, target_y)
        # -----------------------------------------------------

    def send_goal_to_nav2(self, x, y):
        """发送目标点给 Nav2 并处理动作反馈"""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = self.global_frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.position.z = 0.0
        # 简单起见，不设置朝向角（四元数使用默认的无旋转）
        goal_msg.pose.pose.orientation.w = 1.0

        self.nav_client.wait_for_server()
        self.is_navigating = True

        # 异步发送目标
        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        """目标发送后的回调，获取结果的 future"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("[?] Nav2 rejects this target. Target may lay in obstacles")
            self.is_navigating = False
            return

        self.get_logger().info("[*] Nav2 received goal. Navigating to the aim target...")
        self.current_goal_handle = goal_handle

        # 监听执行结果
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        """导航完成后的回调"""
        status = future.result().status
        # Enum values: 4 = SUCCEEDED, 5 = CANCELED, 6 = ABORTED
        if status == 4:
            self.get_logger().info("[*] Arrived at target. Preparing to the next scan...")
        else:
            self.get_logger().warn(f"[?] Navigation has been canceled: {status}")

        # 无论成功失败，都释放标志位，让定时器在下一帧计算新边界
        self.is_navigating = False

def main(args=None):
    rclpy.init(args=args)
    node = ExplorerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()