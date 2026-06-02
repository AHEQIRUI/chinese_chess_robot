#!/usr/bin/env python3
"""
YOLO物体检测与抓取程序
使用YOLOv8检测物体并根据形状分类执行抓取序列
"""

import cv2
import numpy as np
import json
import sys
import time

sys.path.insert(0, 'src')

try:
    from ultralytics import YOLO
except ImportError:
    print("错误: 无法导入ultralytics")
    YOLO = None

try:
    from Arm_Lib import Arm_Device
except ImportError:
    print("警告: 无法导入Arm_Lib")
    Arm_Device = None


# 颜色分类HSV范围
COLOR_RANGES = {
    '红': {'lower': [(0, 50, 50), (156, 50, 50)], 'upper': [(10, 255, 255), (180, 255, 255)]},
    '橙': {'lower': [(11, 50, 50)], 'upper': [(25, 255, 255)]},
    '黄': {'lower': [(26, 50, 50)], 'upper': [(34, 255, 255)]},
    '绿': {'lower': [(35, 50, 50)], 'upper': [(77, 255, 255)]},
    '青': {'lower': [(78, 50, 50)], 'upper': [(99, 255, 255)]},
    '蓝': {'lower': [(100, 50, 50)], 'upper': [(124, 255, 255)]},
    '红': {'lower': [(125, 50, 50)], 'upper': [(155, 255, 255)]},
    '粉': {'lower': [(0, 20, 20), (156, 20, 20)], 'upper': [(10, 255, 255), (180, 255, 255)]},
}

COLOR_BGR = {
    'red': (0, 0, 255), 'orange': (0, 165, 255), 'yellow': (0, 255, 255),
    'green': (0, 255, 0), 'cyan': (255, 255, 0), 'blue': (255, 0, 0),
    'purple': (128, 0, 128), 'pink': (255, 192, 203), 'black': (0, 0, 0),
    'white': (255, 255, 255), 'gray': (128, 128, 128), 'unknown': (255, 255, 255),
    'dark_purple': (139, 0, 139), 'dark_red': (0, 0, 139),
    'dark_yellow': (0, 200, 200), 'dark_green': (0, 100, 0),
}


def classify_color_simple(roi):
    """使用HSV颜色空间识别物体颜色"""
    if roi.size == 0:
        return 'unknown', 0.0

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    avg_hsv = np.mean(hsv, axis=(0, 1))
    h, s, v = avg_hsv

    print(f"    HSV: H={h:.1f}, S={s:.1f}, V={v:.1f}")

    # 优先判断黑色：亮度很低时直接判定为黑色
    if v < 80:
        return 'black', 0.9

    # 判断白色和灰色：饱和度很低且亮度较高
    if s < 30:
        if v > 200:
            return 'cyan', 0.8
        elif v >= 80:
            return 'cyan', 0.8

    # 深色系：亮度较低但有饱和度
    if v < 100:
        if h < 10 or h > 170:
            return 'red', 0.8
        elif 10 <= h < 25:
            return 'black', 0.8
        elif 25 <= h < 35:
            return 'yellow', 0.8
        elif 35 <= h < 85:
            return 'green', 0.8
        elif 85 <= h < 120:
            return 'blue', 0.8
        elif 120 <= h < 170:
            return 'red', 0.8

    # 正常亮度颜色判断
    if h < 10 or h > 170:
        return 'red', 0.8
    elif 10 <= h < 25:
        return 'yellow', 0.8
    elif 25 <= h < 35:
        return 'yellow', 0.8
    elif 35 <= h < 85:
        return 'green', 0.8
    elif 85 <= h < 120:
        return 'blue', 0.8
    elif 120 <= h < 170:
        return 'red', 0.8

    return 'unknown', 0.0


class YOLOGraspTester:
    def __init__(self, model_path='models/best.pt'):
        if Arm_Device:
            self.arm = Arm_Device()
            print("机械臂已连接")
        else:
            self.arm = None

        if YOLO:
            print(f"加载YOLO模型: {model_path}...")
            self.model = YOLO(model_path)
            print("模型加载完成")
        else:
            self.model = None

        with open('config/camera_config.json', 'r') as f:
            calib = json.load(f)
            self.camera_matrix = np.array(calib['camera_matrix'])
            self.dist_coeffs = np.array(calib['dist_coeffs'])

        # 相机位置
        self.cam_pos = np.array([0.04, 0.002, 0.68])
        self.grasp_height = 0.02  # 2cm

        # 初始位置
        self.initial_pos = [90, 179, 0, 0, 90, 65]

        # 放置位置 (x, y, z cm)
        self.place_pos = (-25, 10, 20)

        print(f"相机位置: {self.cam_pos}")
        print(f"夹取高度: {self.grasp_height} m")

    def pixel_to_robot(self, u, v, z_depth):
        """像素坐标转机器人坐标 (米)"""
        pixel_hom = np.array([u, v, 1.0])
        cam_intrinsic_inv = np.linalg.inv(self.camera_matrix)
        cam_coords = cam_intrinsic_inv @ pixel_hom
        cam_offsets = cam_coords[:2] * z_depth

        robot_x = -self.cam_pos[1] - cam_offsets[1]
        robot_y = self.cam_pos[0] - cam_offsets[0]
        robot_z = self.cam_pos[2] - z_depth

        return np.array([robot_x, robot_y, robot_z])

    def solve_ik(self, position):
        """使用ik.py求解IK"""
        try:
            import ik
        except ImportError:
            print("错误: 无法导入ik.py")
            return None

        x, y, z = position
        x_cm, y_cm, z_cm = x * 100, y * 100, z * 100

        valid, deg1, deg2, deg3, deg4 = ik.backward_kinematics(x_cm, y_cm, z_cm)

        if valid:
            return [deg1, deg2, deg3, deg4, 90]
        else:
            print(f"IK无解: ({x_cm:.1f}, {y_cm:.1f}, {z_cm:.1f})")
            return None

    def detect_objects(self, frame, conf_threshold=0.5):
        """检测物体并分类颜色"""
        if self.model is None:
            return []

        results = self.model(frame, conf=conf_threshold, verbose=False)
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

                # 只使用物体中间部分进行颜色识别
                h, w = roi.shape[:2]
                margin_x, margin_y = int(w * 0.25), int(h * 0.25)
                roi_center = roi[margin_y:h-margin_y, margin_x:w-margin_x]

                color, color_conf = classify_color_simple(roi_center)

                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                # 使用相机内参估算深度
                z_depth = self.cam_pos[2] - self.grasp_height
                robot_pos = self.pixel_to_robot(cx, cy, z_depth)

                detections.append({
                    'box': (x1, y1, x2, y2),
                    'object': cls_name,
                    'color': color,
                    'conf': conf,
                    'color_conf': color_conf,
                    'center': (cx, cy),
                    'robot_pos': robot_pos,
                    'grasp_pos': np.array([robot_pos[0], robot_pos[1], self.grasp_height])
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
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)
            cv2.circle(frame, det['center'], 5, color_bgr, -1)

            # 显示机器人坐标
            pos = det['robot_pos']
            pos_text = f"Robot: ({pos[0]*100:.1f}, {pos[1]*100:.1f}, {pos[2]*100:.1f}) cm"
            cv2.putText(frame, pos_text, (x1, y2 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        return frame

    def set_initial_position(self):
        """移动到初始位置"""
        if self.arm:
            self.arm.Arm_serial_servo_write6(
                self.initial_pos[0], self.initial_pos[1], self.initial_pos[2],
                self.initial_pos[3], self.initial_pos[4], self.initial_pos[5], 2000
            )
            print(f"移动到初始位置: {self.initial_pos}")

    def move_to_position(self, position, servo5_angle=None, servo6_angle=57, retries=3, use_servo5_formula=False):
        """移动到指定位置，带重试机制

        Args:
            use_servo5_formula: True时当舵机4<40度使用servo5-90+servo1调整
        """
        angles = self.solve_ik(position)
        if angles is None:
            print(f"无法到达位置: {position}")
            return False

        servo1 = angles[0]
        servo4 = angles[3]
        servo5_raw = servo5_angle if servo5_angle else angles[4]

        if use_servo5_formula and servo4 < 10:
            servo5 = angles[4] - 90 + servo1
            print(f"  舵机4={servo4:.1f}°<40°,舵机5调整为{servo5:.1f}°({angles[4]}-90+{servo1})")
        else:
            servo5 = 90  # 保持舵机5为90度

        if self.arm:
            for attempt in range(retries):
                try:
                    self.arm.Arm_serial_servo_write6(
                        angles[0], angles[1], angles[2],
                        servo4, servo5, servo6_angle, 2000
                    )
                    print(f"移动到 {position}: [{angles[0]:.1f}, {angles[1]:.1f}, {angles[2]:.1f}, {servo4}, {servo5}, {servo6_angle}]")
                    return True
                except Exception as e:
                    print(f"I2C错误 (尝试 {attempt+1}/{retries}): {e}")
                    time.sleep(0.5)
            print(f"移动失败: {position}")
            return False
        return False

    def open_gripper(self):
        """打开夹爪"""
        if self.arm:
            self.arm.Arm_serial_servo_write(6, 57, 800)
            print("打开夹爪")

    def close_gripper(self):
        """关闭夹爪"""
        if self.arm:
            self.arm.Arm_serial_servo_write(6, 140, 800)
            print("关闭夹爪")

    def grasp_sequence(self, grasp_pos, place_pos, gripper_close_angle=140, gripper_open_angle=57, object_type='cube'):
        """执行完整的抓取序列

        Args:
            grasp_pos: 抓取位置
            place_pos: 放置位置
            gripper_close_angle: 夹爪闭合角度,默认140
            gripper_open_angle: 夹爪张开角度,默认57
            object_type: 物体类型,默认'cube'
        """
        print("\n===== 开始抓取序列 =====")

        # 1. 移动到初始位置
        print("1. 移动到初始位置")
        self.set_initial_position()
        time.sleep(2.0)

        # 2. 移动到物体上方 (只用1cm,避免超出工作空间)
        above_pos = (grasp_pos[0], grasp_pos[1], grasp_pos[2] + 0.01)
        print(f"2. 移动到物体上方 {above_pos}")
        if not self.move_to_position(above_pos, servo6_angle=gripper_open_angle, use_servo5_formula=True):
            print("警告: 上方位置不可达,跳过")
            above_pos = grasp_pos
        time.sleep(2.0)

        # 3. 根据舵机4角度和物体类型调整抓取高度
        angles_check = self.solve_ik(grasp_pos)
        is_pyramid = (object_type == 'pyramid')
        if angles_check and angles_check[3] < 10 and is_pyramid:
            grasp_height_adjusted = 0.01  # 1cm
            print(f"3a. 舵机4角度{angles_check[3]:.1f}°<40°且物体为pyramid,设置抓取高度为1cm")
        else:
            grasp_height_adjusted = 0.02  # 2cm
            print(f"3a. 抓取高度为2cm")

        grasp_pos_adjusted = np.array([grasp_pos[0], grasp_pos[1], grasp_height_adjusted])

        # 3b. 下降到抓取高度
        print(f"3b. 下降到抓取位置 {grasp_pos_adjusted}")
        if not self.move_to_position(grasp_pos_adjusted, servo6_angle=gripper_open_angle, use_servo5_formula=True):
            print("错误: 无法移动到抓取位置,取消抓取")
            return
        time.sleep(3.0)

        # 4. 关闭夹爪
        print(f"4. 抓取物体 (闭合角度: {gripper_close_angle})")
        if self.arm:
            self.arm.Arm_serial_servo_write(6, gripper_close_angle, 800)
        time.sleep(1.0)

        # 5. 抬起到安全高度 (z=20cm, y轴减2cm)
        print("5. 抬起到安全高度")
        safe_pos = (grasp_pos[0], grasp_pos[1] - 0.02, 0.20)
        if not self.move_to_position(safe_pos, servo6_angle=gripper_close_angle):
            print("警告: 抬起失败,继续执行")
        time.sleep(2.0)

        # 6. 移动到放置位置上方 (保持z=20cm安全高度)
        above_place = (place_pos[0] / 100, place_pos[1] / 100, 0.20)
        print(f"6. 移动到放置位置上方 {above_place}")
        if not self.move_to_position(above_place, servo6_angle=gripper_close_angle):
            print("警告: 放置上方位置不可达")
        time.sleep(2.0)

        # 7. 下降到放置位置
        place_pos_m = (place_pos[0] / 100, place_pos[1] / 100, place_pos[2] / 100)
        print(f"7. 下降到放置位置 {place_pos_m}")
        if not self.move_to_position(place_pos_m, servo6_angle=gripper_close_angle):
            print("警告: 放置位置不可达")
        time.sleep(2.0)

        # 8. 打开夹爪
        print("8. 放置物体")
        self.open_gripper()
        time.sleep(1.0)

        # 9. 抬起到安全高度
        print("9. 抬起到安全高度")
        self.move_to_position(above_place, servo6_angle=57)
        time.sleep(2.0)

        # 10. 返回初始位置
        print("10. 返回初始位置")
        self.set_initial_position()

        print("\n===== 抓取序列完成 =====")

    def run(self):
        """运行测试"""
        if self.model is None:
            print("YOLO模型未加载,退出")
            return

        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("\n===== YOLO物体抓取程序 =====")
        print("按 'd' 检测物体")
        print("按 'g' 执行抓取(选中的目标)")
        print("按 'q' 退出\n")

        cv2.namedWindow('YOLO Grasp')

        selected_idx = None
        detections = []
        mouse_pos = (0, 0)  # 当前鼠标像素坐标

        def mouse_callback(event, x, y, flags, param):
            nonlocal selected_idx, detections, mouse_pos
            mouse_pos = (x, y)
            if event == cv2.EVENT_LBUTTONDOWN:
                for i, det in enumerate(detections):
                    x1, y1, x2, y2 = det['box']
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        selected_idx = i
                        print(f"选中目标 {i+1}: {det['color']} {det['object']}")
                        break

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 去畸变
                h, w = frame.shape[:2]
                new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
                    self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h))
                frame = cv2.undistort(frame, self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)

                display = frame.copy()

                # 绘制所有检测结果
                display = self.draw_detections(display, detections)

                # 绘制选中状态
                if selected_idx is not None and selected_idx < len(detections):
                    det = detections[selected_idx]
                    x1, y1, x2, y2 = det['box']
                    cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    label = f"[已选择] {det['color']} {det['object']}"
                    cv2.putText(display, label, (x1, y1 - 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # 显示状态
                status = f"检测: {len(detections)} 个 | 已选择: {selected_idx+1 if selected_idx is not None else '-'}"
                cv2.putText(display, status, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                # 显示鼠标位置的相机坐标
                mx, my = mouse_pos
                z_depth = self.cam_pos[2] - self.grasp_height
                cam_coord = self.pixel_to_robot(mx, my, z_depth)
                cam_text = f"Camera: ({mx}, {my}) -> ({cam_coord[0]*100:.1f}, {cam_coord[1]*100:.1f}, {cam_coord[2]*100:.1f}) cm"
                cv2.putText(display, cam_text, (10, 55),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                cv2.putText(display, "d: detect | g: grasp | q: quit | click: select", (10, 460),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                cv2.imshow('YOLO Grasp', display)
                cv2.setMouseCallback('YOLO Grasp', mouse_callback)

                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break
                elif key == ord('d'):
                    detections = self.detect_objects(frame)
                    selected_idx = None
                    print(f"\n检测到 {len(detections)} 个物体:")
                    for i, det in enumerate(detections):
                        pos = det['robot_pos']
                        print(f"  {i+1}. {det['color']} {det['object']} @ pixel{det['center']}")
                        print(f"     机器人坐标: ({pos[0]*100:.1f}, {pos[1]*100:.1f}, {pos[2]*100:.1f}) cm")
                        print(f"     抓取坐标: ({det['grasp_pos'][0]*100:.1f}, {det['grasp_pos'][1]*100:.1f}, {det['grasp_pos'][2]*100:.1f}) cm")

                elif key == ord('g'):
                    if selected_idx is not None and selected_idx < len(detections):
                        det = detections[selected_idx]
                        print(f"抓取: {det['color']} {det['object']}")
                        # pyramid形状使用150度夹爪角度
                        if det['object'] == 'pyramid':
                            close_angle = 150
                            open_angle = 10
                        else:
                            close_angle = 133
                            open_angle = 10
                        self.grasp_sequence(det['grasp_pos'], self.place_pos, close_angle, open_angle, det['object'])
                    else:
                        print("请先点击选择目标")

        finally:
            cap.release()
            cv2.destroyAllWindows()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='xq.pt', help='YOLO模型路径')
    args = parser.parse_args()

    tester = YOLOGraspTester(model_path=args.model)
    tester.run()