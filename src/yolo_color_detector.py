#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO颜色检测程序
使用YOLOv5预训练模型检测物体并分类颜色
"""

import cv2
import numpy as np
from ultralytics import YOLO
import time
from collections import Counter


COLOR_RANGES = {
    '红': {
        'lower': [(0, 50, 50), (156, 50, 50)],
        'upper': [(10, 255, 255), (180, 255, 255)]
    },
    '橙': {
        'lower': [(11, 50, 50)],
        'upper': [(25, 255, 255)]
    },
    '黄': {
        'lower': [(26, 50, 50)],
        'upper': [(34, 255, 255)]
    },
    '绿': {
        'lower': [(35, 50, 50)],
        'upper': [(77, 255, 255)]
    },
    '青': {
        'lower': [(78, 50, 50)],
        'upper': [(99, 255, 255)]
    },
    '蓝': {
        'lower': [(100, 50, 50)],
        'upper': [(124, 255, 255)]
    },
    '紫': {
        'lower': [(125, 50, 50)],
        'upper': [(155, 255, 255)]
    },
    '粉': {
        'lower': [(0, 20, 20), (156, 20, 20)],
        'upper': [(10, 255, 255), (180, 255, 255)]
    },
}


COLOR_BGR = {
    '红': (0, 0, 255),
    '橙': (0, 165, 255),
    '黄': (0, 255, 255),
    '绿': (0, 255, 0),
    '青': (255, 255, 0),
    '蓝': (255, 0, 0),
    '紫': (128, 0, 128),
    '粉': (255, 192, 203),
    '黑': (0, 0, 0),
    '白': (255, 255, 255),
    '灰': (128, 128, 128),
}


def classify_color_by_hsv(roi):
    """使用HSV颜色空间分类颜色"""
    if roi.size == 0:
        return '未知'
    
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    color_counts = {}
    
    for color_name, ranges in COLOR_RANGES.items():
        lower_bounds = ranges['lower']
        upper_bounds = ranges['upper']
        
        mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
        
        for lower, upper in zip(lower_bounds, upper_bounds):
            lower_np = np.array(lower)
            upper_np = np.array(upper)
            temp_mask = cv2.inRange(hsv_roi, lower_np, upper_np)
            mask = cv2.bitwise_or(mask, temp_mask)
        
        pixel_count = cv2.countNonZero(mask)
        color_counts[color_name] = pixel_count
    
    gray_mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
    for lower, upper in [
        ([0, 0, 0], [180, 255, 46]),
        ([0, 0, 46], [180, 255, 255]),
        ([0, 0, 0], [180, 43, 255]),
    ]:
        temp_mask = cv2.inRange(hsv_roi, np.array(lower), np.array(upper))
        gray_mask = cv2.bitwise_or(gray_mask, temp_mask)
    
    black_pixels = cv2.countNonZero(gray_mask)
    total_pixels = roi.shape[0] * roi.shape[1]
    
    gray_mask_white = cv2.inRange(hsv_roi, np.array([0, 0, 180]), np.array([180, 25, 255]))
    white_pixels = cv2.countNonZero(gray_mask_white)
    
    if black_pixels > total_pixels * 0.5:
        return '黑'
    elif white_pixels > total_pixels * 0.7:
        return '白'
    elif black_pixels > total_pixels * 0.15 and white_pixels < total_pixels * 0.3:
        return '灰'
    else:
        max_color = max(color_counts, key=color_counts.get)
        if color_counts[max_color] > total_pixels * 0.1:
            return max_color
    
    return '未知'


def classify_color_simple(roi):
    """简化的颜色分类方法"""
    if roi.size == 0:
        return '未知', 0.0
    
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    
    h_mean = np.mean(h)
    s_mean = np.mean(s)
    v_mean = np.mean(v)
    
    total_pixels = roi.shape[0] * roi.shape[1]
    
    if v_mean < 40:
        return '黑', 0.9
    elif v_mean > 220 and s_mean < 30:
        return '白', 0.9
    elif s_mean < 30:
        if v_mean > 100:
            return '灰', 0.8
        else:
            return '黑', 0.7
    
    color_ranges = [
        ('红', 0, 10, (0, 255, 255)),
        ('橙', 11, 25, (0, 165, 255)),
        ('黄', 26, 40, (0, 255, 255)),
        ('绿', 41, 80, (0, 255, 0)),
        ('青', 81, 100, (255, 255, 0)),
        ('蓝', 101, 130, (255, 0, 0)),
        ('紫', 131, 160, (128, 0, 128)),
        ('粉', 161, 180, (255, 192, 203)),
    ]
    
    best_color = '未知'
    best_score = 0.0
    
    for color_name, h_min, h_max, bgr in color_ranges:
        if h_min <= h_mean <= h_max:
            confidence = min(1.0, (180 - abs(h_mean - (h_min + h_max) / 2)) / 90 + 0.3)
            if confidence > best_score:
                best_score = confidence
                best_color = color_name
    
    return best_color, best_score


class YOLODetector:
    """YOLO颜色检测器"""
    
    def __init__(self, model_name='yolov8n.pt', camera_id=0, conf_threshold=0.5):
        self.camera_id = camera_id
        self.conf_threshold = conf_threshold
        self.cap = None
        self.model = None
        self.frame_count = 0
        self.fps = 0
        self.fps_start_time = time.time()
        
        print(f"加载YOLO模型: {model_name}...")
        self.model = YOLO(model_name)
        print("模型加载完成")
    
    def open_camera(self):
        """打开摄像头"""
        print(f"正在打开摄像头 /dev/video{self.camera_id}...")
        self.cap = cv2.VideoCapture(self.camera_id)
        
        if not self.cap.isOpened():
            print(f"错误：无法打开摄像头")
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"摄像头已打开: {width}x{height}")
        return True
    
    def close_camera(self):
        """关闭摄像头"""
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()
        print("摄像头已关闭")
    
    def process_frame(self, frame):
        """处理单帧图像"""
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = result.names[cls_id]
                
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                
                roi = frame[y1:y2, x1:x2]
                
                color, color_conf = classify_color_simple(roi)
                
                if color == '未知':
                    continue
                
                detections.append({
                    'box': (x1, y1, x2, y2),
                    'object': cls_name,
                    'color': color,
                    'conf': conf,
                    'color_conf': color_conf,
                    'center': ((x1 + x2) // 2, (y1 + y2) // 2),
                })
        
        return detections
    
    def draw_detections(self, frame, detections):
        """绘制检测结果"""
        for det in detections:
            x1, y1, x2, y2 = det['box']
            color = det['color']
            color_bgr = COLOR_BGR.get(color, (255, 255, 255))
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color_bgr, 2)
            
            label = f"{color} {det['object']} {det['conf']*100:.1f}%"
            
            (label_w, label_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            
            cv2.rectangle(
                frame,
                (x1, y1 - label_h - 10),
                (x1 + label_w, y1),
                color_bgr,
                -1
            )
            
            cv2.putText(
                frame, label, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )
            
            cx, cy = det['center']
            cv2.circle(frame, (cx, cy), 5, color_bgr, -1)
        
        return frame
    
    def print_detections(self, detections):
        """打印检测结果到控制台"""
        if not detections:
            return
        
        print(f"\n检测到 {len(detections)} 个物体:")
        print("-" * 50)
        for i, det in enumerate(detections, 1):
            cx, cy = det['center']
            print(f"{i}. 颜色: {det['color']:4s} | 物体: {det['object']:10s} | "
                  f"置信度: {det['conf']*100:5.1f}% | 位置: ({cx:3d}, {cy:3d})")
        print("-" * 50)
    
    def run(self):
        """运行检测循环"""
        if not self.open_camera():
            return
        
        print("\n=== YOLO颜色检测 ===")
        print("按 'q' 退出")
        print("按 's' 截图")
        print("=" * 40)
        
        last_print_time = time.time()
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("错误：无法读取帧")
                break
            
            self.frame_count += 1
            
            if time.time() - self.fps_start_time >= 1.0:
                self.fps = self.frame_count / (time.time() - self.fps_start_time)
                self.frame_count = 0
                self.fps_start_time = time.time()
            
            detections = self.process_frame(frame)
            
            frame = self.draw_detections(frame, detections)
            
            info_text = [
                f"FPS: {self.fps:.1f}",
                f"检测: {len(detections)} 个物体",
                "q:退出 s:截图"
            ]
            
            for i, text in enumerate(info_text):
                cv2.putText(
                    frame, text, (10, 25 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                )
            
            cv2.imshow("YOLO Color Detection", frame)
            
            if time.time() - last_print_time >= 2.0 and detections:
                self.print_detections(detections)
                last_print_time = time.time()
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"detection_{timestamp}.jpg"
                cv2.imwrite(filename, frame)
                print(f"截图已保存: {filename}")
        
        self.close_camera()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='YOLO颜色检测')
    parser.add_argument('--model', type=str, default='yolov8n.pt',
                        help='YOLO模型名称或路径')
    parser.add_argument('--camera', type=int, default=0,
                        help='摄像头设备ID')
    parser.add_argument('--conf', type=float, default=0.5,
                        help='置信度阈值')
    args = parser.parse_args()
    
    detector = YOLODetector(
        model_name=args.model,
        camera_id=args.camera,
        conf_threshold=args.conf
    )
    
    try:
        detector.run()
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        detector.close_camera()
        print("程序结束")


if __name__ == "__main__":
    main()
