#!/usr/bin/env python3
"""
YOLOv8n 图片目标检测脚本
对指定图片进行目标检测，标注物体类别和颜色
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os


def get_dominant_color(image, bbox, center_ratio=0.5):
    """
    获取边界框中心区域的主要颜色

    Args:
        image: BGR 图像
        bbox: 边界框 [x1, y1, x2, y2]
        center_ratio: 中心区域占比 (0-1)，默认0.5表示使用中心50%区域

    Returns:
        颜色名称 (中文)
    """
    x1, y1, x2, y2 = map(int, bbox)

    # 确保边界在图像范围内
    h, w = image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return "unknown"

    # 计算中心区域
    box_w = x2 - x1
    box_h = y2 - y1
    margin_w = int(box_w * (1 - center_ratio) / 2)
    margin_h = int(box_h * (1 - center_ratio) / 2)

    # 裁剪中心区域
    cx1 = x1 + margin_w
    cx2 = x2 - margin_w
    cy1 = y1 + margin_h
    cy2 = y2 - margin_h

    # 确保有效区域
    cx1, cy1 = max(0, cx1), max(0, cy1)
    cx2, cy2 = min(w, cx2), min(h, cy2)

    if cx2 <= cx1 or cy2 <= cy1:
        return "unknown"

    # 裁剪目标中心区域
    roi = image[cy1:cy2, cx1:cx2]

    # 转换到 HSV 颜色空间
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 计算平均颜色
    avg_hsv = np.mean(hsv, axis=(0, 1))
    h, s, v = avg_hsv

    # 打印 HSV 值用于调试
    print(f"    HSV: H={h:.1f}, S={s:.1f}, V={v:.1f}")

    # 优先判断黑色：亮度很低时直接判定为黑色
    # 黑色物体的特征：亮度极低（V < 40），无论饱和度如何
    if v < 80:
        return "black"

    # 判断白色和灰色：饱和度很低且亮度较高
    if s < 30:
        if v > 200:
            return "cyan"
        elif v >= 80:
            return "cyan"

    # 根据色调判断颜色（亮度足够且有饱和度的情况）
    # 深色系：亮度较低但有饱和度
    if v < 100:
        # 深色调物体，根据色调判断但加"深"前缀
        if h < 10 or h > 170:
            return "red"
        elif 10 <= h < 25:
            return "black"
        elif 25 <= h < 35:
            return "yellow"
        elif 35 <= h < 85:
            return "green"
        elif 85 <= h < 100:
            return "blue"
        elif 100 <= h < 125:
            return "blue"
        elif 125 <= h < 145:
            return "dark_purple"
        elif 145 <= h < 170:
            return "red"

    # 正常亮度颜色判断
    if h < 10 or h > 170:
        return "red"
    elif 10 <= h < 25:
        return "yellow"
    elif 25 <= h < 35:
        return "yellow"
    elif 35 <= h < 85:
        return "green"
    elif 85 <= h < 100:
        return "blue"
    elif 100 <= h < 125:
        return "blue"
    elif 125 <= h < 145:
        return "purple"
    elif 145 <= h < 170:
        return "red"

    return "unknown"


def get_color_bgr(color_name):
    """
    根据颜色名称返回 BGR 值用于绘制
    """
    color_map = {
        "red": (0, 0, 255),
        "orange": (0, 165, 255),
        "yellow": (0, 255, 255),
        "green": (0, 255, 0),
        "cyan": (255, 255, 0),
        "blue": (255, 0, 0),
        "purple": (255, 0, 255),
        "pink": (203, 192, 255),
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "gray": (128, 128, 128),
        "dark_red": (0, 0, 139),
        "dark_orange": (0, 100, 200),
        "dark_yellow": (0, 200, 200),
        "dark_green": (0, 100, 0),
        "dark_cyan": (139, 139, 0),
        "dark_blue": (139, 0, 0),
        "dark_purple": (139, 0, 139),
        "dark_pink": (139, 100, 200),
        "unknown": (128, 128, 128),
    }
    return color_map.get(color_name, (128, 128, 128))


def detect_image(image_path, model, show_debug=False, save_result=True):
    """
    对单张图片进行目标检测

    Args:
        image_path: 图片路径
        model: YOLO模型
        show_debug: 是否显示调试信息
        save_result: 是否保存结果图片

    Returns:
        检测结果列表
    """
    # 读取图片
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"无法读取图片: {image_path}")
        return None

    print(f"处理图片: {image_path}")
    print(f"图片尺寸: {frame.shape[1]}x{frame.shape[0]}")

    # YOLOv8 推理
    results = model(frame, verbose=False)

    # 获取检测结果
    detections = results[0].boxes
    detection_list = []

    if detections is not None and len(detections) > 0:
        print(f"检测到 {len(detections)} 个目标")

        for i, box in enumerate(detections):
            # 获取边界框坐标
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # 获取类别和置信度
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            cls_name = model.names[cls_id]

            # 获取物体颜色
            color_name = get_dominant_color(frame, [x1, y1, x2, y2])
            color_bgr = get_color_bgr(color_name)

            # 保存检测信息
            detection_info = {
                'class': cls_name,
                'color': color_name,
                'confidence': conf,
                'bbox': [x1, y1, x2, y2]
            }
            detection_list.append(detection_info)

            # 输出检测结果
            print(f"  目标 {i+1}: {cls_name} | 颜色: {color_name} | 置信度: {conf:.2f}")

            # 绘制边界框
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color_bgr, 2)

            # 绘制标签背景
            label = f"{cls_name} | {color_name} | {conf:.2f}"
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            cv2.rectangle(
                frame,
                (int(x1), int(y1) - text_h - 10),
                (int(x1) + text_w, int(y1)),
                color_bgr,
                -1
            )

            # 绘制标签文字
            cv2.putText(
                frame,
                label,
                (int(x1), int(y1) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            # 显示调试信息
            if show_debug:
                # 绘制中心点
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                cv2.circle(frame, (int(cx), int(cy)), 5, (0, 0, 255), -1)

                # 显示坐标
                debug_text = f"({int(cx)}, {int(cy)})"
                cv2.putText(
                    frame,
                    debug_text,
                    (int(cx) + 10, int(cy)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1
                )

    else:
        print("未检测到任何目标")

    # 显示检测数量
    det_count = len(detections) if detections is not None else 0
    cv2.putText(
        frame,
        f"Detections: {det_count}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )

    # 保存结果图片
    if save_result and det_count > 0:
        # 生成保存路径
        base_name = os.path.splitext(image_path)[0]
        result_path = f"{base_name}_result.jpg"
        cv2.imwrite(result_path, frame)
        print(f"结果已保存: {result_path}")

    return detection_list, frame


def main():
    # 加载训练好的模型
    model_path = "runs/detect/train/weights/best.pt"
    print(f"加载模型: {model_path}")
    
    if not os.path.exists(model_path):
        print(f"模型文件不存在: {model_path}")
        print("请确保模型文件路径正确")
        return
    
    model = YOLO(model_path)
    print(f"检测类别: {model.names}")

    # 设置要检测的图片路径
    # 方式1: 直接指定图片路径
    image_path = "m1.jpg"  # 修改为你的图片路径
    
    # 方式2: 交互式输入（取消下面的注释使用）
    # image_path = input("请输入图片路径: ").strip()
    
    # 检查图片是否存在
    if not os.path.exists(image_path):
        print(f"图片文件不存在: {image_path}")
        print("请修改 image_path 变量为正确的图片路径")
        return

    # 执行检测
    show_debug = True  # 是否显示调试信息
    save_result = True  # 是否保存结果图片
    
    result, annotated_image = detect_image(image_path, model, show_debug, save_result)

    if result is not None:
        # 显示结果图片
        cv2.imshow("Detection Result", annotated_image)
        print("\n控制键:")
        print("  按任意键关闭窗口")
        
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # 打印汇总信息
        if len(result) > 0:
            print("\n检测汇总:")
            for i, det in enumerate(result):
                print(f"  {i+1}. {det['class']} (颜色: {det['color']}, 置信度: {det['confidence']:.2f})")
    else:
        print("检测失败")


def detect_multiple_images(image_folder, model, output_folder="results"):
    """
    批量处理文件夹中的所有图片
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # 支持的图片格式
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    
    # 获取所有图片文件
    image_files = [f for f in os.listdir(image_folder) 
                   if f.lower().endswith(image_extensions)]
    
    if not image_files:
        print(f"在 {image_folder} 中未找到图片文件")
        return
    
    print(f"找到 {len(image_files)} 张图片，开始批量处理...")
    
    for img_file in image_files:
        img_path = os.path.join(image_folder, img_file)
        result, annotated_image = detect_image(img_path, model, show_debug=False, save_result=True)
        
        if result and annotated_image is not None:
            # 保存到输出文件夹
            output_path = os.path.join(output_folder, f"result_{img_file}")
            cv2.imwrite(output_path, annotated_image)
            print(f"已保存: {output_path}")
    
    print("批量处理完成")


if __name__ == "__main__":
    # 单张图片检测
    main()
    
    # 如果需要批量处理文件夹中的图片，取消下面的注释
    # model_path = "runs/detect/train/weights/best.pt"
    # model = YOLO(model_path)
    # detect_multiple_images("images_folder", model)  # 修改为你的图片文件夹路径
