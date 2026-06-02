#!/usr/bin/env python3
"""
摄像头图像采集脚本 - 用于YOLO训练
按 's' 保存当前帧，按 'q' 退出
"""

import cv2
import os
import time
import argparse


def main():
    parser = argparse.ArgumentParser(description='YOLO训练图像采集')
    parser.add_argument('--output', '-o', type=str, default='yolo_dataset',
                        help='输出文件夹路径')
    parser.add_argument('--camera', '-c', type=int, default=0,
                        help='摄像头设备号')
    parser.add_argument('--prefix', '-p', type=str, default='img',
                        help='图片前缀名')
    args = parser.parse_args()

    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"错误: 无法打开摄像头 /dev/video{args.camera}")
        return

    print(f"\n===== YOLO训练图像采集 =====")
    print(f"输出目录: {os.path.abspath(output_dir)}")
    print(f"按 's' 保存当前帧")
    print(f"按 'q' 退出")
    print("=" * 40)

    count = 0
    last_save_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("错误: 无法读取帧")
            break

        display = frame.copy()

        # 显示提示信息
        cv2.putText(display, f"按 's' 保存图片", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 显示已保存数量
        cv2.putText(display, f"已保存: {count} 张", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow('YOLO Image Capture', display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('s'):
            # 防抖：避免快速连续保存
            current_time = time.time()
            if current_time - last_save_time < 0.5:
                print("保存过于频繁，请稍后")
                continue
            last_save_time = current_time

            # 生成文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{args.prefix}_{timestamp}_{count:04d}.jpg"
            filepath = os.path.join(output_dir, filename)

            cv2.imwrite(filepath, frame)
            count += 1
            print(f"已保存: {filepath}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n采集完成，共保存 {count} 张图片")


if __name__ == '__main__':
    main()