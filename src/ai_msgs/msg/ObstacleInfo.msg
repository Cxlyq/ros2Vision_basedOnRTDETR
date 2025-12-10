# 物体类别ID
int32 id

# 物体类别名称
string label

# 置信度
float32 score

# --- 核心位置信息 ---

# 1. 绝对位置 (在 Odom 坐标系下的位置，用于记忆)
geometry_msgs/Point position_odom

# 2. 相对距离 (相对于机器人中心，用于快速避障判断)
# distance: 直线距离
# lateral: 水平偏移 (左正右负)
float32 distance
float32 lateral

# (可选) 速度信息，以后做卡尔曼滤波需要用到
# geometry_msgs/Vector3 velocity