# N10 Lidar 配置
## 安装依赖
```shell
sudo apt-get install ros-humble-diagnostic-updater
sudo apt-get install libpcap-dev
```
## 挂载lidar并重命名串口
拔插雷达，并均在宿主机执行
```shell
lsusb
```
对照设备变化。本N10雷达设备号为1a86:55d4
确认设备号后，在宿主机执行以下命令
```shell
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", MODE:="0777", SYMLINK+="wheeltec_lidar"' | sudo tee /etc/udev/rules.d/wheeltec_n10_lidar.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```
确认挂载是否成功
```shell
apt-get update
apt-get install usbutils -y
ls -l /dev/wheeltec_lidar
```
### 编译lslidar ros2驱动包
```shell
colcon build --packages-select lslidar_msgs lslidar_driver
```
## 启动N10雷达
```shell
ros2 launch lslidar_driver lsn10_launch.py
```
## Lidar输出话题
```shell
/scan
/x10/lslidar_driver_node/transition_event
/x10/lslidar_point_cloud
/x10/motor_control
/x10/time_topic
```