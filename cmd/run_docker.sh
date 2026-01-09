#!/bin/bash
xhost +local:root

IMAGE_NAME="dustynv/ros:humble-pytorch-l4t-r35.3.1"

HOST_WORK_DIR="/mnt/Y560SSD/Projects"

DOCKER_WORK_DIR="/root/Projects"

sudo docker run -it --rm \
    --runtime=nvidia \
    --network host \
    --env="DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --env="http_proxy=http://127.0.0.1:10808"\
    --env="https_proxy=http://127.0.0.1:10808"\
    --env="ROS2_DOMAIN_ID=30"\
    --env="export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"\
    --env="export CYCLONEDDS_URI='<CycloneDDS><Domain><General><NetworkInterfaceAddress>wlan0</NetworkInterfaceAddress></General></Domain></CycloneDDS>'"\
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$HOST_WORK_DIR:$DOCKER_WORK_DIR" \
    --volume="/dev/bus/usb:/dev/bus/usb" \
    $IMAGE_NAME \
    bash
