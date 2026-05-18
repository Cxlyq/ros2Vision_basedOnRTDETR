# Gemini相机配置
## 安装依赖
```shell
sudo apt install libgflags-dev  ros-$ROS_DISTRO-image-geometry ros-$ROS_DISTRO-camera-info-manager\
ros-$ROS_DISTRO-image-transport ros-$ROS_DISTRO-image-publisher libgoogle-glog-dev libusb-1.0-0-dev libeigen3-dev
```
## 在宿主机上安装依赖
```shell
sudo apt install libusb-1.0-0-dev
```
## 在宿主机挂载
```shell
cd src/astra_camera/scripts
sudo bash install.sh
sudo udevadm control --reload-rules && sudo udevadm trigger
```
## 在docker中安装驱动必须组件
```shell
cd lib/libuvc
mkdir build && cd build
cmake .. && make -j4
sudo make install
sudo ldconfig
```
## 编译ros2驱动包
```shell
colcon build --event-handlers  console_direct+  --cmake-args  -DCMAKE_BUILD_TYPE=Release
```
## 启动gemini相机
```shell
ros2 launch astra_camera gemini.launch.xml
```
## Camera输出话题
```shell
/camera/color/camera_info
/camera/color/image_raw
/camera/depth/camera_info
/camera/depth/image_raw
/camera/depth/points
/camera/ir/camera_info
/camera/ir/image_raw
```