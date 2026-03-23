# Camera utils节点
提供关于相机的初始工具，目前仅有双目相机拆分工具

## Splitter node 双目相机拆分
### Input topic
input topic: 由ros2 usb_cam package发布，内容为原始image_raw Image

### Output topic
pub_left_img: 发布拆分后的左侧相机Image话题
pub_right_img： 发布拆分后的右侧相机Image话题
pub_left_info： 发布左侧相机内参，来自于launch文件中的left_yaml_path路径
pub_right_info：发布右侧相机内参，来自于launch文件中的right_yaml_path路径

### Launch
输入
```shell
ls /dev/video*
```
查看摄像头列表。通过反复插拔确认目标摄像头后，更改参数'video_device'

输入
```shell
sudo apt-get install v4l2-utils
v4l2-ctl -d /dev/video0 --list-formats-ext
```
查看相机参数并修改video_device下的参数

根据实际位置修改'left_yaml_path'与'right_yaml_path'
## 使用节点
### 启动节点
```shell
ros2 launch camera_utils camera_launch.py
```
查看画面
```shell
# 宿主机上输入
xhost +
# docker上输入
ros2 run rqt_image_view rqt_image_view
```
相机标定
```shell
ros2 run camera_calibration cameracalibrator \
  --size 8x6 \
  --square 0.025 \
  --approximate 0.0 \
  --no-service-check \
  right:=/right/image_raw \
  left:=/left/image_raw
  
mkdir ~/calib_result
tar -xvf /tmp/calibrationdata.tar.gz -C ~/calib_result
```