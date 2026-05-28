#!/bin/bash

# 允许本地的 root 用户访问 X Server（Docker 容器默认以 root 运行）
xhost +local:root

IMAGE_NAME="ros2-dveformer-env:v1.0"
HOST_WORK_DIR="/mnt/Y560SSD/Projects"
DOCKER_WORK_DIR="/root/Projects"
HOST_DATA_DIR="/mnt/Y560SSD/Data/ros_saved_data"
DOCKER_DATA_DIR="/root/ros_exported_data"

sudo docker run -it --rm \
    --runtime=nvidia \
    --network host \
    --ipc=host \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --env="http_proxy=http://127.0.0.1:10808" \
    --env="https_proxy=http://127.0.0.1:10808" \
    --env="ROS2_DOMAIN_ID=30" \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    --privileged \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$HOST_WORK_DIR:$DOCKER_WORK_DIR" \
    --volume="$HOST_DATA_DIR:$DOCKER_DATA_DIR" \
    --volume="/dev:/dev" \
    $IMAGE_NAME \
    bash