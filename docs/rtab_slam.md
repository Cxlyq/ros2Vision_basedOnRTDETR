# RTAB SLAM 建图
标准化、广泛应用的SLAM方法

## 启动
1. 启动虚拟场景与小车
```shell
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py world:=maze
```
2. 启动RTAB SLAM
```shell
ros2 launch rtab_slam rtab_map.launch.py
```

3. 启动teleop keyboard控制器
```shell
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

## 话题输出
- /rtabmap/grid_map (类型: nav_msgs/msg/OccupancyGrid)
  - 内容： 2D 占据栅格地图
- /rtabmap/cloud_map (类型: sensor_msgs/msg/PointCloud2)
  - 内容： 拼接好的 3D 全局点云地图
- /rtabmap/localization_pose (类型: geometry_msgs/msg/PoseWithCovarianceStamped)
  - 内容： 机器人在地图上的精确全局坐标（X, Y, Z 以及旋转姿态），并附带置信度（协方差）

## Launch参数说明
RTAB-MAP是一个极其强大的多传感器融合框架。它主要支持以下三大类信息
- 视觉信息 (Visual)：
  - RGB-D 相机： 彩色图像 (RGB) + 深度图 (Depth)。
  - 双目相机 (Stereo)： 左目图像 + 右目图像（RTAB-Map 会自行计算视差和深度）。
- 激光雷达 (LiDAR)：
  - 2D 激光雷达 (Scan)： 输出单线距离数据。
  - 3D 激光雷达 (Point Cloud)： 输出三维点云数据（如 Velodyne, Ouster）。
- 本体感受与运动估计 (Odometry/Proprioception)：
  - 里程计 (Odometry)： 轮式里程计、视觉里程计 (VO)、激光里程计 (LO)。RTAB-Map 需要一个先验的里程计输入（通常通过 TF 树中的 odom -> base_link 提供）。
  - IMU 数据： 用于重力对齐和高频运动补偿。

本节点采用以下关键参数
```python
parameters = [{
    'frame_id': 'base_link',  # 机器人的中心坐标系
    'use_sim_time': True,  # 使用 Gazebo 仿真时钟
    'subscribe_depth': True,  # 订阅深度图
    'subscribe_scan': True,  # 订阅 2D 激光雷达
    'approx_sync': True,  # 允许时间戳微小偏差
    'queue_size': 20,

    # 算法调优
    'Grid/FromDepth': 'false',  # 用雷达(/scan)建2D地图，比用深度图更清晰
    'Reg/Strategy': '1',  # 优先使用雷达(ICP)来纠正里程计
    'RGBD/NeighborLinkRefining': 'true'
}]
```
- Reg/Strategy 决定 RTAB-Map 在优化位姿和检测回环时主要依赖哪种传感器进行配准
  - 0 视觉特征匹配 依赖相机
  - 1 迭代最近点算法 依赖雷达
  - 2 视觉 + ICP 联合配准 综合使用
- Grid/FromDepth决定是否使用深度图建2D地图
  - true 使用
  - false 不使用
- RGBD/NeighborLinkRefining
  - 强制 RTAB-Map 在相邻的两个位姿节点（Neighbor Links）之间，再做一次额外的对齐（配准）计算，以修正局部的里程计漂移。

在室内 2D 建图和结构化环境的里程计校正中，激光雷达 (LiDAR) 的准确度远高于深度相机 (Depth)。
但是，视觉也有不可替代的优势，RTAB-Map 极其依赖视觉的“词袋模型 (Bag-of-Words)”来进行全局回环检测 (Loop Closure)
最优解是相机负责“认路”（全局回环），雷达负责“画图”（2D 占据栅格地图）和“微调位姿”（ICP 配准）。

### 开启3D占据地图输出
配置参数
```python
parameters = [{
'Grid/3D': 'true', # 开启3D 建图，在内存中构建一个三维的体素网格（Voxel Grid）或八叉树地图（OctoMap）
'Grid/FromDepth': 'true', # 切换建图数据源, RTAB-Map 将读取 OAK-D 深度相机生成的 3D 点云，把这些带有高度信息的数据拼接成 3D 空间

# 调优参数
'Grid/RangeMax': '3.0', # 截断距离。OAK-D 深度相机超过 3~4 米后，深度估算会变得极其离谱
'Grid/DepthDecimation': '4', # 深度图降采样, 把计算量骤降到原来的 1/16
'Grid/CellSize': '0.05', # 3D 地图的体素（Voxel）大小。0.05 意味着地图是由一个个 5厘米 x 5厘米 x 5厘米 的小方块拼成的
'Grid/RayTracing': 'true' # 3D 空间清理。如果仿真环境里有移动的物体，或者建图时产生了噪点，光线追踪机制可以通过相机的视线去“看透”并“清除”那些原本被误判为障碍物的透明/空白区域。
}]
```
使用rviz2查看3D占据地图
```shell
ros2 run rviz2 rviz2 # 将 Topic 选为 /rtabmap/cloud_map
```

## RTAB VIZ界面说明
- Odometry（里程计板块）
  - 位于左下角，这里显示的是相机当前这一刻看到的实时画面，并且叠加了系统提取到的“视觉特征点”
  - 功能：用于判断当前机器人移动的稳定性和视觉里程计的健康度
  - 颜色表示：
    - 背景色： 正常情况下是黑色。如果背景变暗黄色 (Dark Yellow)，警告当前环境特征太少（比如面对一堵大白墙），快要迷失了；如果变暗红色 (Dark Red)，说明视觉里程计彻底跟丢了（Odometry Lost）。
    - 特征点颜色： 绿色是高质量的匹配点（Inliers），黄色是没匹配上的点，红色是错误点（Outliers）
- Loop closure detection（回环检测板块）
  - 分为上下两个子窗口
    - 上窗口（当前帧）：这是机器人此刻拍下的画面，蓝色背景： 代表这是一个新提取的特征签名，它正在向历史数据库发出询问
    - 下窗口（回忆帧/假设帧）：这是词袋模型从历史记忆中翻出来的一张最相似的旧照片，RTAB-Map 尝试把上下两张图里的特征点连线（图片中那些细细的蓝线），看看能不能对得上
      - 🟢 绿色： 回环接受 (Accepted)! 两张图的特征点连线又多又准，系统确信：“我来过这里！”，随即在后台拉扯地图，消除累积误差。
      - 🔴 红色： 回环拒绝 (Rejected)! 就像你截图里显示的 Loop hypothesis 435 rejected!。系统觉得这两张图虽然有点像，但细看特征点（细蓝线）匹配得太少或者逻辑不对，为了安全起见，拒绝认亲。
      - 🟡 黄色： 回环疑似/待定。 相似度得分很高，但可能由于空间几何检验没通过（比如虽然看起来像同一个房间，但雷达测距发现房间大小不对），最终被拒绝。
- 3D Map（3D/2D 混合地图板块）
  - 位于右侧最大的区域。这里展示的是一个非常漂亮的 2D 占据栅格地图 (Occupancy Grid Map)
    - 白色区域： 机器人探索过的安全、无障碍的自由空间。
    - 青色/蓝绿色线条： 这是你的 2D 激光雷达（RPLidar）扫描到的坚实墙壁或障碍物轮廓。
    - 黑色区域： 尚未探索的未知领域。
    - 白色轨迹线（图中交织的细线）： 机器人的历史移动轨迹（Graph Nodes 的连线）。

## 警告处理
## 官方文档与论文资料
https://wiki.ros.org/rtabmap_slam
https://arxiv.org/abs/2403.06341
https://introlab.github.io/rtabmap/
https://github.com/introlab/rtabmap
