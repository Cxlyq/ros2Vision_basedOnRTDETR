# Stereo image Node

畸变校正 (Rectification): 利用 CameraInfo (K, D, R, P 矩阵)，把鱼眼或有畸变的画面拉平，并让左右摄像头的像素行对齐（极线对齐）。

视差计算 (Disparity): 对比左右图，计算像素的偏移量，生成视差图（Disparity Map）和点云（Point Cloud）。

该节点本质上是众多ROS2官方库打包成容器，通过launch文件启动运行
包括以下容器：
- 简单的TF树发布
- 左/右畸变矫正
- 视差计算
- 点云生成

## 环境准备
```shell
sudo apt install ros-humble-image-pipeline
```

## 使用节点
### 运行节点
```shell
ros2 launch stereo_image stereo_proc.launch.py
```
### 查看点云
```shell
ros2 run rviz2 rviz2
```