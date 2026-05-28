# Docker Tips
向Jetson Axive上部署该项目时，由于JetsonPack版本老旧等问题，ROS2可能无法原生运行在本机上
推荐使用docker运行本项目

## Docker install
```shell
sudo apt-get install docker.io
```

## 配置Docker网络环境
### Docker在宿主机的网络环境
涉及到docker从dockerHub下载镜像等场景。 
- 添加代理设置文件
```shell
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo vi /etc/systemd/system/docker.service.d/http-proxy.conf
```
- 写入配置
```shell
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:20171"
Environment="HTTPS_PROXY=http://127.0.0.1:20172"
Environment="NO_PROXY=localhost,127.0.0.1,::1,/var/run/docker.sock"
```
- 载入设置
```shell
sudo systemctl daemon-reload
sudo systemctl restart docker
```
- 验证配置是否生效
```shell
sudo systemctl show --property=Enviroment docker
```
### Docker内部的网络环境
需要在启动脚本里设置-env http_proxy https_proxy

## 配置Docker存储环境
因为Jetson开发版自带空间小，因此必须外挂硬盘使用。

! 注意，因为Jetson供电问题，必须限制硬盘访问速度，否则会频繁掉电掉盘。

- 挂载硬盘

```shell
sudo mkdir -p /mnt/ssd
sudo mount /dev/sda1 /mnt/ssd
sudo chmod -R 777 /mnt/ssd
```

- 设置开机挂载
获取UUID
```shell
# 获取 UUID
sudo blkid /dev/sda1
```
写入fstab
```shell
sudo vi /etc/fstab
-- 添加：UUID=你的UUID粘贴在这里  /mnt/ssd  ext4  defaults  0  2
```

- 更改docker配置

创建docker存储目录
```shell
sudo mkdir -p /mnt/ssd/docker_image
```
修改daemon
```shell
sudo systemctl stop docker
sudo vi /etc/docker/daemon.json
```
```json
{
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    },
    "default-runtime": "nvidia",
    "data-root": "/mnt/ssd/docker-data"
}
```
```shell
sudo systemctl start docker
```
## 开启Jetson高性能模式，并验证Docker可访问GPU
- 开启Jetson高性能模式：
```bash
sudo nvpmodel -m 0
sudo jetson_clocks
```
- 安装NVIDIA Container Toolkit
```bash
sudo apt install -y nvidia-docker2
```
- 验证GPU穿透
```bash
sudo systemctl restart docker
sudo docker run --rm --runtime=nvidia --gpus all nvcr.io/nvidia/l4t-base:r35.3.1 nvidia-smi
```

## 拉取开发镜像
```bash
sudo docker pull dustynv/ros:humble-pytorch-l4t-r35.3.1
```