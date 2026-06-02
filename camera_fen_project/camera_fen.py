#!/usr/bin/env python3
"""
USB摄像头中国象棋棋盘识别 - 输出FEN码
按 SPACE 捕捉当前帧并识别
按 ESC 退出
"""

import cv2
import numpy as np
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.chessboard_detector import ChessboardDetector


def main():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 模型路径
    pose_model_path = os.path.join(script_dir, "onnx/pose/4_v6-0301.onnx")
    full_classifier_model_path = os.path.join(script_dir, "onnx/layout_recognition/nano_v3-0319.onnx")

    # 初始化检测器
    print("正在加载模型...")
    detector = ChessboardDetector(
        pose_model_path=pose_model_path,
        full_classifier_model_path=full_classifier_model_path
    )

    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误: 无法打开摄像头")
        return

    print("摄像头已打开")
    print("按 SPACE 捕捉并识别 | 按 ESC 退出")

    window_name = "Chinese Chess Recognition - Press SPACE to capture, ESC to exit"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("错误: 无法读取摄像头帧")
            break

        # 显示画面
        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            print("退出程序")
            break
        elif key == 32:  # SPACE
            # 转换颜色空间
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 识别棋盘
            _, transformed_image, cells_labels, scores, time_info = detector.pred_detect_board_and_classifier(frame_rgb)

            if cells_labels and len(cells_labels) > 0:
                # 生成FEN码
                fen = detector.to_fen(cells_labels, scores)

                # 计算平均置信度
                avg_score = np.mean(scores) if scores else 0

                # 输出结果
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] FEN: {fen}")
                print(f"置信度: {avg_score*100:.1f}% | {time_info}")
            else:
                print("未能识别到棋盘，请调整角度后重试")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()