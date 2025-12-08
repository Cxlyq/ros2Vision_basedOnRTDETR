import torch
import torchvision.transforms as T
from PIL import Image, ImageDraw, ImageFont
from src.core import YAMLConfig
import os

# ================= 配置区域 =================
# 1. 图片路径
IMAGE_PATH = 'test.jpg' 
OUTPUT_PATH = 'result_v2.jpg'

# 2. RT-DETRv2 的权重文件 (请确认文件名是否完全一致)
# 注意：你提到的文件名是 rtdetrv2_r50vd_x6_coco_full.pth (注意是 6x 还是 x6，一般官方是 6x)
# 这里假设你下载的文件名如下，如果不同请修改：
CHECKPOINT = './../weights/rtdetrv2_r50vd_6x_coco_full.pth'

# 3. RT-DETRv2 的配置文件
# 官方仓库中 v2 的配置通常在 configs/rtdetrv2/ 目录下
CONFIG = './configs/rtdetrv2/rtdetrv2_r50vd_6x_coco.yml'

# 4. 设备
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# COCO 80类 ID对应表
CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
    'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
    'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
    'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
    'hair drier', 'toothbrush'
]
# ===========================================

def main():
    print(f"Using device: {DEVICE}")

    # --- 1. 实例化模型 ---
    print(f"Loading config from {CONFIG}...")
    if not os.path.exists(CONFIG):
        print(f"❌ 错误：找不到配置文件 {CONFIG}")
        print("请检查 configs/rtdetrv2/ 目录是否存在，或者是否需要更新代码仓库。")
        return

    try:
        conf = YAMLConfig(CONFIG, resume=None)
        model = conf.model.to(DEVICE)
        model.eval()
    except Exception as e:
        print(f"❌ 模型构建失败: {e}")
        print("可能是代码仓库版本旧，缺少 RT-DETRv2 的源码。建议 git pull 更新一下。")
        return

    # --- 2. 加载权重 (复用之前的成功逻辑) ---
    print(f"Loading checkpoint from {CHECKPOINT}...")
    if not os.path.exists(CHECKPOINT):
        print(f"❌ 错误：找不到权重文件 {CHECKPOINT}")
        return

    checkpoint = torch.load(CHECKPOINT, map_location='cpu')
    
    # 智能提取 state_dict
    if 'ema' in checkpoint:
        print("ℹ️ 使用 EMA 权重 (精度更高)")
        state_dict = checkpoint['ema']['module'] if 'module' in checkpoint['ema'] else checkpoint['ema']
    elif 'model' in checkpoint:
        print("ℹ️ 使用 Model 权重")
        state_dict = checkpoint['model']
    else:
        state_dict = checkpoint

    # 去除 module. 前缀
    new_state_dict = {}
    for k, v in state_dict.items():
        if k.startswith('module.'):
            new_state_dict[k[7:]] = v
        else:
            new_state_dict[k] = v
            
    # 加载
    msg = model.load_state_dict(new_state_dict, strict=False)
    print(f"权重加载完毕。Missing keys: {len(msg.missing_keys)}")

    # --- 3. 预处理 ---
    if not os.path.exists(IMAGE_PATH):
        print(f"❌ 错误：找不到图片 {IMAGE_PATH}")
        return

    im_pil = Image.open(IMAGE_PATH).convert('RGB')
    w, h = im_pil.size
    print(f"Image Size: {w}x{h}")

    transforms = T.Compose([
        T.Resize((640, 640)),
        T.ToTensor(),
        # RT-DETR 全系列都使用 ImageNet 标准归一化
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    im_data = transforms(im_pil).unsqueeze(0).to(DEVICE)

    # --- 4. 推理 ---
    print("Inference starting...")
    with torch.no_grad():
        output = model(im_data)

    scores = output['pred_logits'].sigmoid()
    boxes = output['pred_boxes']

    # --- 5. 结果解析 ---
    # 降低阈值来看看狗是不是分数比较低
    threshold = 0.35 
    
    # 取第一张图结果
    scores = scores[0]
    boxes = boxes[0]
    
    # 获取每个框的最大类别分数
    max_scores, class_ids = scores.max(dim=1)
    keep = max_scores > threshold

    print(f"Found {keep.sum()} objects (Threshold: {threshold})")

    # 绘图准备
    draw = ImageDraw.Draw(im_pil)
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except:
        font = ImageFont.load_default()

    # 遍历画框
    for i in range(len(scores)):
        if keep[i]:
            score = max_scores[i].item()
            class_id = class_ids[i].item()
            box = boxes[i].cpu().numpy()
            
            # 类别名称
            label = CLASSES[class_id]
            
            # 还原坐标
            cx, cy, bw, bh = box
            cx, cy, bw, bh = cx*w, cy*h, bw*w, bh*h
            x1, y1, x2, y2 = cx-bw/2, cy-bh/2, cx+bw/2, cy+bh/2
            
            # 打印检测到的东西
            print(f"👉 Detected: {label} ({score:.2f})")

            # 画框 (狗用蓝色，猫用红色，其他绿色)
            color = 'green'
            if label == 'cat': color = 'red'
            if label == 'dog': color = 'blue'

            draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
            
            # 文字标签
            text = f"{label} {score:.2f}"
            # 绘制文字背景
            draw.rectangle([x1, y1-30, x1+150, y1], fill=color)
            draw.text((x1+5, y1-30), text, fill='white', font=font)

    im_pil.save(OUTPUT_PATH)
    print(f"✅ 结果已保存至 {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
