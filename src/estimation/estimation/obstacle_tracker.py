import rclpy
from rclpy.time import Time

class Obstacle:
    def __init__(self, o_id, label, score, position_odom):
        self.obstacle_id = o_id
        self.obstacle_label = label
        self.obstacle_score = score
        self.obstacle_position_odom = position_odom
        self.obstacle_last_update_time = rclpy.time.Time()