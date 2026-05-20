# 1. 基于你刚刚导入本地的 PyTorch 镜像
FROM dustynv/l4t-pytorch:r36.4.0

# 接收构建时传入的代理环境变量
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY

# 避免安装过程中的交互提示卡死
ENV DEBIAN_FRONTEND=noninteractive

# 2. 安装基础工具并设置语言环境 (ROS2 强烈要求)
RUN apt-get update && apt-get install -y curl gnupg2 lsb-release locales && \
    locale-gen en_US en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8

# 3. 添加 ROS2 密钥和清华大学镜像源 (加速下载)
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu jammy main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

RUN sed -i 's@ports.ubuntu.com/ubuntu-ports@mirrors.tuna.tsinghua.edu.cn/ubuntu-ports@g' /etc/apt/sources.list

# 4. 安装 ROS2 Humble Desktop 及编译工具
RUN apt-get update && \
    apt-get install -y ros-humble-desktop python3-colcon-common-extensions && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
	ros-humble-usb-cam \
	&& rm -rf /var/lib/apt/lists/*

# 更新软件源并安装 ROS 2 视觉与建图相关的依赖包
RUN apt-get update && apt-get install -y \
    ros-humble-usb-cam \
    ros-humble-rtabmap-ros \
    ros-humble-image-pipeline \
    ros-humble-image-proc \
    ros-humble-stereo-image-proc \
    && rm -rf /var/lib/apt/lists/*

# 5. install Gazebo
ARG DEBIAN_FRONTEND=nointeractive

RUN apt-get update && apt-get install -y \
	ignition-fortress \
	ros-humble-ros-gz \
	ros-humble-ros-gz-sim \
	ros-humble-ros-gz-bridge \
	&& rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
	ros-humble-xacro \
	ros-humble-joint-state-publisher-gui \
	ros-humble-teleop-twist-keyboard \
	ros-humble-laser-filters \
	ros-humble-turtlebot4-simulator \
	&& rm -rf /var/lib/apt/lists/*

# 6. Install Turtlebot4
RUN apt-get update && apt-get install -y \
	ros-humble-turtlebot4-simulator \
	ros-humble-turtlebot4-desktop \
    ros-humble-turtlebot4-navigation \
    ros-humble-irobot-create-nodes \
    ros-humble-irobot-create-description \
    ros-humble-irobot-create-msgs \
    ros-humble-ros-gz \
    ros-humble-xacro \
	&& rm -rf /var/lib/apt/lists/*

# 7. Install dependancy for Gemini Pro Cam and N10 lidar
RUN apt-get update && apt-get install -y \
	ros-humble-diagnostic-updater \
	libpcap-dev \
	libgflags-dev \
	ros-humble-image-geometry \
	ros-humble-camera-info-manager \
	ros-humble-image-transport \
	ros-humble-image-publisher \
	libgoogle-glog-dev \
	libusb-1.0-0-dev \
	libeigen3-dev \
	&& rm -rf /var/lib/apt/lists/*

# 8. 自动配置环境变量，这样一进容器就能用 ros2 命令
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

CMD ["bash"]