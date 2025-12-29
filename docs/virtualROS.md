# ROS虚拟环境安装启动说明
## 安装
! 全程注意不要启动conda虚拟环境
```bash
conda deactivate
```
安装TurtleBot3与Gazebot
- apt update: 由于官方库更新频繁，上架新版本会撤下老版本，所以必须update，并且有必要清空之前的update缓存：
```bash
# 清理旧的下载包
sudo apt clean

# 强制删除 apt 的列表缓存（相当于把菜单撕了重新拿一份）
sudo rm -rf /var/lib/apt/lists/*

# 重新生成缓存
sudo apt update

# 再次安装
sudo apt install ros-humble-turtlebot3
```
- 安装
```bash
# 1. 安装 TurtleBot3 的 ROS 2 包
sudo apt update
sudo apt install ros-humble-turtlebot3 -y
sudo apt install ros-humble-turtlebot3-gazebo ros-humble-turtlebot3-simulations -y

# 2. 安装 Gazebo 仿真相关包
sudo apt install ros-humble-gazebo-ros-pkgs -y
```
- 下载虚拟环境需要的模型：如果不下载，启动Gazebot图形界面时会异常卡住
```bash
# 1. 创建模型目录
mkdir -p ~/.gazebo/models

# 2. 进入目录
cd ~/.gazebo/models

# 3. 从 GitHub 克隆模型库（这里使用 Gitee 镜像，速度快，适合国内或网络不佳环境）
git clone https://github.com/osrf/gazebo_models.git .

# 注意：上面命令最后有个点 "."，表示克隆到当前目录
```
- 配置环境变量：指定模型位置和使用的模型
```bash
echo 'export TURTLEBOT3_MODEL=waffle_pi' >> ~/.bashrc
echo 'export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models' >> ~/.zshrc
source ~/.zshrc
```

## 使用
- 启动仿真世界(terminal 1)
```bash
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```
- 启动键盘控制(terminal 2)
```bash
ros2 run turtlebot3_teleop teleop_keyboard
```
- 查看摄像头画面(terminal 3)
```bash
ros2 run rqt_image_view rqt_image_view
```

## 多端仿真说明
ROS支持多端仿真，即可以在pc1跑虚拟仿真，在pc2接受pc1的topic
启用多端仿真，需要保证ROS_DOMAIN_ID一致
```shell
export ROS_DOMAIN_ID=30
```
为了避免多网卡出现问题，需要使用cyclonedds指定网卡
```shell
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><NetworkInterfaceAddress>wlan0</NetworkInterfaceAddress></General></Domain></CycloneDDS>'
```
jetson **docker** 也进行一样的配置，注意更改网卡名称

docker要添加启动参数--net=host保证网络畅通

Jetson docker image镜像无法安装cyclonedds，需要下载源码编译:
```shell
cd /root/Projects/ros2_vision/src

# 1. 下载 CycloneDDS 核心库 (Humble 对应 0.10.x 版本)
git clone -b releases/0.10.x https://github.com/eclipse-cyclonedds/cyclonedds.git

# 2. 下载 ROS 2 RMW 接口
git clone -b humble https://github.com/ros2/rmw_cyclonedds.git

cd cyclonedds
# 切换低版本，防止无法编译
git checkout releases/0.9.x

cd ../..
# 只编译这两个相关的包，节省时间
colcon build --packages-up-to rmw_cyclonedds_cpp

source install/setup.bash
```

## 意外修复
- 清理多个僵尸进程导致的卡顿
```bash
killall -9 gzserver gzclient
```
- 运行空世界以排查错误：
```bash
ros2 launch gazebo_ros gazebo.launch.py
```
- 手动生成模型
```bash
ros2 run gazebo_ros spawn_entity.py -entity waffle_pi -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_waffle_pi/model.sdf -x -2.0 -y -0.5 -z 0.01
```
- 排查错误参数： verbose:=true