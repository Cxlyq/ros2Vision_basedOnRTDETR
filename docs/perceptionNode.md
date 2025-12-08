# Perception Node识别检测节点
此节点用于接受image，结合rtdetr给出物体检测信息
## Input/Receive
```python
        self.subscription = self.create_subscription(
            Image,  # 消息类型是什么？(提示：看上面的 import)
            '/camera/image_raw',  # Gazebo 的相机话题名是什么？
            self.image_callback,  # 收到图后，交给哪个函数处理？(提示：是下面定义的那个函数)
            10  # QoS (队列长度)
        )
```
## Output/Pubulisher
```python
        self.publisher = self.create_publisher(
            DetectionArray,
            '/brain/detections',
            10
        )
```
## 启动方法
已为该节点配置launch.py，可以通过launch启动
```bash
ros2 launch camera_detector perception.launch.py
```
## 参数说明
参数位于config/rtdetr_config.yaml，通过修改参数可快速配置模型信息
```python
    conf_threshold: 0.45 # 置信度
    weights_file: "rtdetrv2_r50vd_6x_coco_full.pth" # RT_DETR权重文件
    config_file: "rtdetrv2_r50vd_6x_coco.yml" # RT_DETR配置文件
    class_names: [] # RT_DETR类别列表
```
## 编译
最好通过conda环境内置colcon编译，否则需要更改install文件
```bash
colcon build --packages-select camera_detector --symlink-install
source install/setup.zsh
# 修改默认python
head -n 1 install/camera_detector/lib/camera_detector/perception_node
# 改为 
#!/home/cx/anaconda3/envs/rtdetr_ros2/bin/python
```