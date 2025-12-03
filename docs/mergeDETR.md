# 向ROS2中融合RT——DETR
本文档旨在说明如何配置能够兼容运行ROS2与conda下的RT_Detr的环境
1. 生成环境： 
```bash
conda create -n rtdetr_ros2 python=3.10 -y # 本地py版本和conda rt-detr版本必须一致
conda activate rtdetr_ros2
```
2. 安装torch，cudnn，注意版本匹配
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
注意，由于linux包匹配原则，可能会优先匹配系统已存在的包，可能会导致复杂报错。按转时有必要添加强制安装参数
```bash
# --force-reinstall: 强制重新安装
# --ignore-installed: 忽略已存在的包（不管是哪里的）
# --no-cache-dir: 不使用缓存，下载最新的
python -m pip install <package name> --force-reinstall --ignore-installed --no-cache-dir
```
3. 安装其余依赖
```bash
pip install -r requirements.txt
```
4. 降级numpy，cv_bridge不支持2.0以上的numpy
```bash
pip install "numpy<2.0"
```
5. 在conda环境下，引入ROS库目录
```bash
# 进入 Conda 环境的配置目录
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
mkdir -p $CONDA_PREFIX/etc/conda/deactivate.d

# 创建激活脚本：当环境激活时，自动 source ROS 和设置 PYTHONPATH
# 注意：这里我们假设每次都使用 humble。
echo 'source /opt/ros/humble/setup.bash' > $CONDA_PREFIX/etc/conda/activate.d/ros2_bridge.sh
echo 'export OLD_PYTHONPATH=$PYTHONPATH' >> $CONDA_PREFIX/etc/conda/activate.d/ros2_bridge.sh
echo 'export PYTHONPATH=$PYTHONPATH:/opt/ros/humble/lib/python3.10/site-packages' >> $CONDA_PREFIX/etc/conda/activate.d/ros2_bridge.sh

# 创建退出脚本：当环境退出时，恢复原样（虽然 Conda 也会自己处理，但显式写出来更安全）
echo 'export PYTHONPATH=$OLD_PYTHONPATH' > $CONDA_PREFIX/etc/conda/deactivate.d/ros2_bridge.sh
echo 'unset OLD_PYTHONPATH' >> $CONDA_PREFIX/etc/conda/deactivate.d/ros2_bridge.sh
```
6. 刷新conda
```bash
conda deactivate
conda activate rtdetr_ros2
```
7. 测试环境
```python
import torch
import cv_bridge
import rclpy
print("Environment is PERFECT!")
```
