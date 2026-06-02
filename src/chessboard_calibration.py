#!/usr/bin/env python3
"""
棋盘格相机内参标定
"""

import cv2
import numpy as np
import os
import json
import glob


def capture_chessboard_images(camera_id=0, output_folder='calibration_data/',
                              num_images=40, chessboard_size=(5, 8),
                              display_size=(640, 480)):
    """采集棋盘格标定图像"""
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print("无法打开相机!")
        return []

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, display_size[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, display_size[1])

    os.makedirs(output_folder, exist_ok=True)

    captured = []
    print(f"开始捕获 {num_images} 张标定图像...")
    print("按 'c' 捕获图像, 按 'q' 退出")

    while len(captured) < num_images:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, chessboard_size)

        display = frame.copy()
        if found:
            cv2.drawChessboardCorners(display, chessboard_size, corners, found)
            status = f"已检测到棋盘格 ({len(captured)}/{num_images})"
            color = (0, 255, 0)
        else:
            status = f"未检测到棋盘格 ({len(captured)}/{num_images})"
            color = (0, 0, 255)

        cv2.putText(display, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(display, "按 'c' 保存, 'q' 退出", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow('Chessboard Capture', display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c') and found:
            filename = os.path.join(output_folder, f'chess_{len(captured):03d}.jpg')
            cv2.imwrite(filename, frame)
            captured.append(filename)
            print(f"已保存: {filename}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n采集完成，共 {len(captured)} 张图像")
    return captured


def calibrate_camera(image_folder='calibration_data/', chessboard_size=(5, 8),
                     square_size=0.029, output_path='config/camera_config.json'):
    """使用棋盘格标定相机内参"""
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
    objp *= square_size

    objpoints = []
    imgpoints = []

    images = glob.glob(os.path.join(image_folder, '*.jpg'))
    images += glob.glob(os.path.join(image_folder, '*.png'))
    images += glob.glob(os.path.join(image_folder, '*.jpeg'))

    if not images:
        print("未找到标定图像!")
        return None

    print(f"找到 {len(images)} 张标定图像")

    image_size = None
    valid_count = 0

    for fname in sorted(images):
        img = cv2.imread(fname)
        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if image_size is None:
            image_size = gray.shape[::-1]

        ret, corners = cv2.findChessboardCorners(gray, chessboard_size)

        if ret:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            objpoints.append(objp)
            imgpoints.append(corners2)
            valid_count += 1
            print(f"OK: {os.path.basename(fname)} - 检测到角点")

            cv2.drawChessboardCorners(img, chessboard_size, corners2, ret)
            cv2.imshow('Calibration', img)
            cv2.waitKey(100)
        else:
            print(f"跳过: {os.path.basename(fname)} - 角点检测失败")

    cv2.destroyAllWindows()

    if valid_count < 5:
        print(f"错误: 有效图像不足 ({valid_count})")
        return None

    print(f"\n有效图像: {valid_count} 张")

    try:
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            objpoints, imgpoints, image_size, None, None
        )
    except Exception as e:
        print(f"标定失败: {e}")
        return None

    print(f"\n===== 相机内参标定结果 =====")
    print(f"焦距 fx: {mtx[0, 0]:.2f}")
    print(f"焦距 fy: {mtx[1, 1]:.2f}")
    print(f"光心 cx: {mtx[0, 2]:.2f}")
    print(f"光心 cy: {mtx[1, 2]:.2f}")
    print(f"畸变系数: {dist.ravel()}")
    print(f"重投影误差: {ret:.4f}")

    result = {
        'camera_matrix': mtx.tolist(),
        'dist_coeffs': dist.tolist(),
        'image_size': image_size,
        'reprojection_error': float(ret)
    }

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=4)

    print(f"\n标定结果已保存到: {output_path}")
    return result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='棋盘格相机标定')
    parser.add_argument('--mode', choices=['capture', 'calibrate'], default='capture',
                        help='运行模式')
    parser.add_argument('--camera', type=int, default=0, help='相机ID')
    parser.add_argument('--folder', default='calibration_data/', help='图像文件夹')
    parser.add_argument('--num', type=int, default=40, help='采集图像数量')
    parser.add_argument('--chessboard', type=int, nargs=2, default=[5, 8],
                        metavar=('COLS', 'ROWS'), help='棋盘格内角点 (默认 5 8)')
    parser.add_argument('--square', type=float, default=0.029,
                        help='方块边长 单位:米 (默认 0.029)')

    args = parser.parse_args()
    chessboard_size = tuple(args.chessboard)

    if args.mode == 'capture':
        capture_chessboard_images(args.camera, args.folder, args.num, chessboard_size)
    elif args.mode == 'calibrate':
        calibrate_camera(args.folder, chessboard_size, args.square)