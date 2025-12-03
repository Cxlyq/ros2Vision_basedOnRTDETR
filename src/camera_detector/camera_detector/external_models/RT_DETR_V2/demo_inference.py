import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torchvision.transforms as T
from src.core import YAMLConfig

# ================= 配置部分 =================
# 权重文件路径 (请确保下载的文件名一致)
checkpoint_path = './rtdetr_r50vd_6x_coco_from_paddle.pth'
# 配置文件路径
config_path = './configs/rtdetr/rtdetr_r50vd_6x_coco.yml' 
# ===========================================

def main():
    # 1. 检查设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # 2. 加载模型
    try:
        print("Loading model configuration...")
        conf = YAMLConfig(config_path, resume=checkpoint_path)
        model = conf.model.to(device)
        model.eval()
        print("Model loaded successfully!")
    except Exception as e:
        print(f"Error loading model: {e}")
        print("请检查路径是否正确，以及是否在 rtdetr_pytorch 目录下运行")
        return

    # 3. 创建一张虚拟测试图 (生成一个画着红色方块的白色图片)
    # 这样你就不用去网上找图了
    image = Image.new('RGB', (640, 640), color='white')
    draw_input = ImageDraw.Draw(image)
    # 在 (100, 100) 画一个红色的矩形，模拟一个物体
    draw_input.rectangle([100, 100, 300, 400], fill='red', outline='black')
    print("Created dummy test image.")

    # 4. 图像预处理
    transforms = T.Compose([
        T.Resize((640, 640)),
        T.ToTensor(),
    ])
    im_data = transforms(image).unsqueeze(0).to(device)

    # 5. 推理 (Inference)
    print("Running inference...")
    with torch.no_grad():
        output = model(im_data)
    
    # RT-DETR 输出包含: 'pred_logits' (分类分数), 'pred_boxes' (坐标)
    scores = output['pred_logits'].sigmoid()
    boxes = output['pred_boxes']
    
    # 6. 解析结果 (取置信度 > 0.5 的)
    # 注意：COCO数据集里，红色方块可能被误识别成其他东西，或者识别不出，这正常
    # 我们主要看代码能否跑通，以及输出格式是否正确
    topk_scores, topk_indexes = torch.topk(scores.flatten(1), 10)
    print("Inference finished!")
    print(f"Raw Output Keys: {output.keys()}")
    print(f"Scores shape: {scores.shape}")
    print(f"Boxes shape: {boxes.shape}")
    
    # 简单打印前几个检测到的东西
    # 因为是红方块，模型可能会懵，但只要不报错就是成功
    print("\n--- Top Detections ---")
    value, idx = topk_scores[0][0], topk_indexes[0][0]
    category = idx % 80  # COCO有80类
    print(f"Best detection confidence: {value.item():.4f}")
    
    print("\n✅ 环境验证成功！可以开始 ROS 节点开发了。")

if __name__ == "__main__":
    main()
