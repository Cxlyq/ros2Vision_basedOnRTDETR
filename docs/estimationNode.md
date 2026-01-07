# EstimationNode 距离预测节点

## Input/Receive 

接受detection话题，内容为perceptionNode对每一帧画面的检测识别结果

```python
self.subscription = self.create_subscription(
    DetectionArray,
    '/brain/detections',
    self.detection_callback,
    10
)
```

## Output/Publish

发布obstacles话题，将检测结果转化为对障碍物的预测结果发布

```python
self.publisher = self.create_publisher(
    ObstacleArray,
    '/brain/obstacles',
    10
)
```

## 自定义obstacle_tracker类

```python
class ObstacleTracker:
    def __init__(self, o_id: int, o_label: str, o_score: float, o_position_glob: PointStamped, o_distance: float, o_lateral: float, o_last_seen: int):
        self.obstacle_id = o_id
        self.obstacle_label = o_label
        self.obstacle_score = o_score
        self.obstacle_position_glob = o_position_glob
        self.obstacle_distance = o_distance
        self.obstacle_lateral = o_lateral
        self.last_seen = o_last_seen
        self.missed_frames = 0

```

TODO: 修改o_id，使其为每个障碍物生成id，而不是挪用类别id

使用position_glob记录经过base_link->odom转化过后的坐标

last_seen代表目标最后出现的帧数

missed_frames由update_memory函数进行维护，代表某一长期记忆中的障碍物在后续多少帧中没有再次出现

## 工作流程

- 维护帧数统计与系统时间，确保所有目标共享一个时间系
```python
        self.frame_count += 1
        detection_time = msg.header.stamp
```
- 创建坐标转换模板
- 对从detection话题传入的detections逐一处理
  - 提取物品信息
  - 调用calculate_position_from_pixel，基于地面约束法计算物体相对于相机的距离
  - 建立局部坐标点
  - 使用do_transform_point转化为全局坐标
  - 将全局坐标与同其他信息存入obstacle对象内，并存入临时记忆
- 更新记忆
  - 匹配：
    - 寻找距离相对最近的、标签一致的、并且不在盲区内的目标进行匹配
    - 匹配到则加权更新障碍物位置
    - 未匹配到则向长期记忆中直接添加该物体
  - 遗忘：
    - 对长期记忆中的所有物体，如果last_seen不等于当前帧数，则将missed_fram +1，代表本帧本障碍物丢失
    - 如果missed_frame持续丢失指定帧数上限，则清除长期记忆

## 启动过程

已为estimation_node配置了ros launch
```shell
ros2 launch estimation_node estimation.launch.py
```

