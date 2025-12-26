#!/bin/bash

echo "If you see this message, it means something you forget to change params in this bash"
exit

xhost +local:root

# 镜像名称
IMAGE_NAME="dustynv/ros:humble-pytorch-l4t-r35.2.1"

# --- 关键修改：指向 SSD 上的工作空间 ---
HOST_WORK_DIR="/mnt/ssd/ros2_ws"
DOCKER_WORK_DIR="/root/ros2_ws"

sudo docker run -it --rm \
    --runtime=nvidia \
    --network host \
    --env="DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
        # ... 设置代理 ...
    --env="http_proxy=http://127.0.0.1:7890" \
    --env="https_proxy=http://127.0.0.1:7890" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$HOST_WORK_DIR:$DOCKER_WORK_DIR" \
    --volume="/dev/bus/usb:/dev/bus/usb" \
    --device="/dev/video0:/dev/video0" \
    $IMAGE_NAME \
    bash