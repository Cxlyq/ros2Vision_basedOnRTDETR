std_msgs/Header header         # 包含时间戳和坐标系(frame_id: 'map')
float32 voxel_size             # 体素的物理尺寸，如0.1 (代表10cm)
SemanticVoxel[] voxels         # 这一帧提取出的所有语义体素