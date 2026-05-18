# Data sniffer节点
用于更方便的嗅探截取传感器原始数据

目前支持2D雷达数据/相机数据与Odom数据
## 启动
根据需要嗅探的数据类型启动不同的节点
举例：
```shell
ros2 launch data_sniffer sniffer_laserScan.launch.py
```
## 新增数据类型支持
于launch文件夹中，仿照前launch文件创建新的文件。

注意传入参数与自定义节点名
```python
rgb_sniffer_node = Node(
    package='data_sniffer',
    executable='data_sniffer',
    name='rgbImage_sniffer',  # 自定义节点名，防止冲突
    output='screen',
    parameters=[{
        'topic_name': '/camera/color/image_raw',
        'msg_type': 'Image',
        'output_dir': rgb_output_dir,
        'target_fps': 10.0
    }]
)
```
在data_sniffer中，首先补全__init__()策略字典，写明数据类型与回调函数:
```python
self.supported_types = {
    'LaserScan': {'class': LaserScan, 'callback': self.laserscan_callback},
    'Odometry': {'class': Odometry, 'callback': self.odometry_callback},
    'Image': {'class': Image, 'callback': self.image_callback}
}
```
其次，补全回调函数逻辑，从get_filepath()自动获取每帧消息，写明存入格式fmt:
```python
def image_callback(self, msg):
    current_time = time.time()
    # 降频逻辑
    if (current_time - self.last_processed_time) >= self.min_interval:
        self.last_processed_time = current_time
        self.frame_count += 1

        try:
            # 使用 CvBridge 将 ROS Image 消息转换为 OpenCV 的 numpy 数组格式
            # 'passthrough' 表示保持原有的通道数和位深（RGB就是8位3通道，Depth通常是16位单通道）
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')

            # 如果你想保存为彩色 JPG，可以将 '.png' 改为 '.jpg'
            # 注意：深度图（Depth）强烈建议使用 '.png'，因为它是无损压缩，且支持16位数据，JPG会导致深度信息丢失！
            img_path = self.get_filepath('.png')

            self._enqueue_task(img_path, cv_image, write_format='image_file')

        except CvBridgeError as e:
            self.get_logger().error(f"CvBridge Error: {e}")
```
其中，fmt格式字符串是自定义的，为了支持一种消息类型存储多种格式。

最后，补全file_writer_thread()的落盘写入逻辑
```python
elif fmt == 'image_file':
    # 使用 cv2.imwrite 直接写入硬盘。
    # 它会自动根据 filepath 的后缀名（.png, .jpg）来决定编码格式
    cv2.imwrite(filepath, data)
```