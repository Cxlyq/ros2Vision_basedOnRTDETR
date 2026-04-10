#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import csv
import os
import queue
import threading
import math
import time
from datetime import datetime


from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry


class DataExporterNode(Node):
    def __init__(self):
        super().__init__('data_sniffer_node')

        # 1. 参数声明
        self.declare_parameter('topic_name', '/scan')
        self.declare_parameter('msg_type', 'LaserScan')
        self.declare_parameter('output_dir', './exported_data')  # 默认当前目录下的 exported_data 文件夹
        self.declare_parameter('target_fps', 10.0)
        topic_name = self.get_parameter('topic_name').get_parameter_value().string_value
        self.msg_type = self.get_parameter('msg_type').get_parameter_value().string_value
        output_dir = self.get_parameter('output_dir').get_parameter_value().string_value

        self.get_logger().info(f'Init data sniffer: Aim topic [{topic_name}]')

        self.target_fps = self.get_parameter('target_fps').value
        self.min_interval = 1.0 / self.target_fps
        self.last_processed_time = 0.0  # 记录上一次处理的时间戳

        # 2. 目录创建与基础文件名前缀
        os.makedirs(output_dir, exist_ok=True)
        self.safe_topic_name = topic_name.replace('/', '_').strip('_')
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = output_dir

        # 3. 核心机制：线程安全的消息队列
        # 设置 maxsize 限制内存无限制增长。如果硬盘实在太慢，队列满了会直接丢弃新数据并警告
        self.data_queue = queue.Queue(maxsize=5000)
        self.is_running = True
        self.frame_count = 0
        self.saved_count = 0

        # 4. 启动后台独立写入线程
        self.write_thread = threading.Thread(target=self.file_writer_thread)
        self.write_thread.daemon = True  # 设置为守护线程，主程序退出时它也跟着退出
        self.write_thread.start()

        # 5. 策略字典
        self.supported_types = {
            'LaserScan': {'class': LaserScan, 'callback': self.laserscan_callback},
            'Odometry': {'class': Odometry, 'callback': self.odometry_callback}
        }

        # 6. 动态创建订阅者
        if self.msg_type in self.supported_types:
            config = self.supported_types[self.msg_type]
            self.subscription = self.create_subscription(
                config['class'],
                topic_name,
                config['callback'],
                10)  # 这里的 10 是 ROS 2 底层的 QoS 队列深度
            self.get_logger().info(f'Subscribe Successfully！Data will be saved at: {os.path.abspath(self.output_dir)}')
        else:
            self.get_logger().error(f'Unsupported message type: {self.msg_type}。')
            exit(1)

    def get_filepath(self, extension):
        """共用的文件名生成逻辑，根据传入的后缀名生成绝对路径"""
        # 格式示例: scan_20231025_143000_000001.csv
        filename = f"{self.safe_topic_name}_{self.session_timestamp}_{self.frame_count:06d}{extension}"
        return os.path.join(self.output_dir, filename)

    # ================= 消费者线程 (后台写入) =================
    def file_writer_thread(self):
        """独立运行，根据任务指定的格式和路径落盘"""
        while self.is_running or not self.data_queue.empty():
            try:
                task = self.data_queue.get(block=True, timeout=0.5)
                filepath = task['filepath']
                data = task['data']
                fmt = task['format']

                # --- 路由分发：根据 format 决定怎么写文件 ---
                if fmt == 'csv_row':
                    with open(filepath, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(data)

                elif fmt == 'ply_pointcloud':
                    ranges = data['ranges']
                    intensities = data['intensities']
                    angle_min = data['angle_min']
                    angle_increment = data['angle_increment']
                    range_min = data['range_min']
                    range_max = data['range_max']

                    # 检查是否包含强度数据
                    has_intensity = len(intensities) == len(ranges)
                    valid_points = []

                    # 1. 数据清洗与坐标转换
                    for i, r in enumerate(ranges):
                        # 过滤掉 Inf, NaN 以及超出测距范围的无效点
                        if range_min <= r <= range_max and not math.isinf(r) and not math.isnan(r):
                            angle = angle_min + i * angle_increment
                            x = r * math.cos(angle)
                            y = r * math.sin(angle)
                            z = 0.0
                            intensity = intensities[i] if has_intensity else 0.0
                            valid_points.append((x, y, z, intensity))

                    with open(filepath, 'w') as f:
                        # --- 写入 PLY Header ---
                        f.write("ply\n")
                        f.write("format ascii 1.0\n")
                        f.write(f"element vertex {len(valid_points)}\n")
                        f.write("property float x\n")
                        f.write("property float y\n")
                        f.write("property float z\n")
                        if has_intensity:
                            f.write("property float intensity\n")
                        f.write("end_header\n")

                        # --- 写入顶点数据 ---
                        for p in valid_points:
                            if has_intensity:
                                # 保留 4 位小数（毫米级精度）
                                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {p[3]:.4f}\n")
                            else:
                                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")

                else:
                    self.get_logger().error(f"Unknown type: {fmt}")

                self.saved_count += 1
                self.data_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"[ERR] An error occurred while writing file : {e}")

    # ================= 生产者回调 (快速提取并入队) =================
    def _enqueue_task(self, filepath, data, write_format):
        """重构后的入队操作：传入具体的保存任务"""
        task = {
            'filepath': filepath,
            'data': data,
            'format': write_format
        }
        try:
            self.data_queue.put_nowait(task)

            # 进度打印逻辑可以保留在这里，或者移到 callback 中
            if self.frame_count % 50 == 0:
                self.get_logger().info(f'Received {self.frame_count} frames，Queue remained: {self.data_queue.qsize()}')
        except queue.Full:
            self.get_logger().warn('Too slow to save data, current frame was rejected! ', throttle_duration_sec=2.0)

    def laserscan_callback(self, msg):
        current_time = time.time()
        # 降频逻辑：判断距离上次处理是否已经过了足够的时间
        if (current_time - self.last_processed_time) >= self.min_interval:
            self.last_processed_time = current_time
            self.frame_count += 1 # 保证同一帧的多个文件拥有相同的序号
            # 提取生成 PLY 所需的完整上下文数据
            scan_data = {
                'angle_min': msg.angle_min,
                'angle_increment': msg.angle_increment,
                'range_min': msg.range_min,
                'range_max': msg.range_max,
                'ranges': msg.ranges,
                'intensities': msg.intensities
            }
            # 任务 1：保存为 CSV
            csv_path = self.get_filepath('.csv')
            self._enqueue_task(csv_path, msg.ranges, write_format='csv_row')

            # 任务 2：保存为 PLY
            ply_path = self.get_filepath('.ply')
            self._enqueue_task(ply_path, scan_data, write_format='ply_pointcloud')

    def odometry_callback(self, msg): # TODO
        self.frame_count += 1
        # 里程计通常不需要一帧一个文件，如果你想让里程计依然追加到一个文件里，
        # 可以在这里做特殊判断，或者依然一帧一个文件：
        csv_path = self.get_filepath('.csv')
        # ... 提取 x,y,z,qx,qy,qz,qw ...
        data = [0, 0, 0, 0, 0, 0, 0]
        self._enqueue_task(csv_path, data, write_format='csv_row')

    # ================= 节点销毁时的清理工作 =================
    def destroy_node(self):
        try:
            self.get_logger().info('Record stopped...')
        except:
            print('Stopping and cleaning resources. (ROS Context invalid)...')

        self.is_running = False  # 通知后台线程准备退出

        # 阻塞等待后台线程把队列里的剩余数据全部写完
        if self.write_thread.is_alive():
            self.write_thread.join(timeout=3.0)

        print(f'Recording ended, received {self.frame_count} frames，saved {self.saved_count} frames。')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DataExporterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()