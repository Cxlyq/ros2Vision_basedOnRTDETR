from nicr_scene_analysis_datasets.auxiliary_data.embedding_estimation import AlphaCLIPEmbeddingEstimator

# DVEFormer 语义感知节点

论文

> Fischedick, S., Seichter, D., Stephan, B., Schmidt, R., Gross, H.-M. Efficient Prediction of Dense Visual Embeddings via Distillation and RGB-D Transformers, in IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS), pp. 2400-2407, 2025.

Github: https://github.com/TUI-NICR/DVEFormer

本节点参考github仓库中inference.py简化修改而成

## Install

本节点需要安装 dveformer/external_models/DVEFormer/lib中的四个python库，安装顺序如下：

```shell
pip install --no-build-isolation AlphaCLIP
pip install -e panopticapi
pip install -e "nicr_scene_analysis_datasets[withpreparation, withauxiliarydata]"
pip install -e nicr_multitask_scene_analysis
```

## Require

本节点需要结合 rtabmap 与 nav2 节点使用

## Configurate

位于 config/dveformer.yaml 注意配置AlphaCLIP与DVEFormer两个权重的路径

```yaml
dveformer_weights_path:
alpha_clip_ckpt_path:
```

以及ros2话题名称
```yaml
sub_rgb_topic: 
sub_depth_topic: 
sub_aim_topic: 
sub_camera_info_topic: 

pub_aim_encode_topic: 
pub_voxel_topic: 
```

## Input topic
- camera_info: 相机内参，推荐订阅深度相机内参，simpleDVE需要据此来2D-3D投射
- aim_text: 用户指令，传入信息应当是对于目标物体的直接描述
- rgb/depth: 由深度相机获取的一组RGB-D图像，默认640*480，需要深度图与RGB图对齐

## Publish topic
- aim_encode: 目标物体文本描述+简单Prompt(内置于节点中)经过AlphaCLIP的编码信息
- voxel_topic: 带有语义信息的体素块组

## Start
```shell
colcon build --packages-select dveformer --symlink-install
source install/setup.bash
ros2 launch dveformer dveformer.launch.py
```