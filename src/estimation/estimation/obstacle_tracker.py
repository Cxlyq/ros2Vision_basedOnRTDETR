from geometry_msgs.msg import PointStamped

# TODO: 修改o_id，使其为每个障碍物生成id，而不是挪用类别id
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
