#!/usr/bin/env python3
"""
抓取测试脚本 - 使用原始ik.py的逆运动学
"""

import cv2
import numpy as np
import json
import sys
import time

try:
    import ik
except ImportError:
    print("错误: 无法导入ik.py")
    ik = None

try:
    from Arm_Lib import Arm_Device
except ImportError:
    print("警告: 无法导入Arm_Lib")
    Arm_Device = None


class GraspingTester:
    def __init__(self):
        if Arm_Device:
            self.arm = Arm_Device()
            print("机械臂已连接")
        else:
            self.arm = None

        # 加载相机内参
        with open('config/camera_config.json', 'r') as f:
            calib = json.load(f)
            self.camera_matrix = np.array(calib['camera_matrix'])
            self.dist_coeffs = np.array(calib['dist_coeffs'])

        # 相机位置
        self.cam_pos = np.array([0.0, 0.14, 0.82])  # X=0居中, Y=14cm(左侧), Z=57cm(高度)
        self.grasp_height = 0.04  # 4cm

        # 初始位置
        # [servo1, servo2, servo3, servo4, servo5, servo6]
        self.initial_pos = [90, 179, 0, 0, 90, 65]

        # 放置位置 (x, y, z cm)
        self.place_pos = (15, 10, 10)

        print(f"相机位置: {self.cam_pos}")
        print(f"夹取高度: {self.grasp_height} m")

    def pixel_to_robot(self, u, v, z_depth):
        """像素坐标转机器人坐标 (米)"""
        pixel_hom = np.array([u, v, 1.0])
        cam_intrinsic_inv = np.linalg.inv(self.camera_matrix)
        cam_coords = cam_intrinsic_inv @ pixel_hom
        cam_offsets = cam_coords[:2] * z_depth

        robot_x = self.cam_pos[0] + cam_offsets[0]
        robot_y = self.cam_pos[1] - cam_offsets[1]
        robot_z = self.cam_pos[2] - z_depth

        return np.array([robot_x, robot_y, robot_z])

    def solve_ik(self, position):
        """使用ik.py求解IK"""
        if ik is None:
            return None

        x, y, z = position
        # ik.py使用cm为单位
        x_cm = x * 100
        y_cm = y * 100
        z_cm = z * 100

        valid, deg1, deg2, deg3, deg4 = ik.backward_kinematics(x_cm, y_cm, z_cm)

        if valid:
            return [deg1, deg2, deg3, deg4, 90]  # J5=90, 夹爪
        else:
            print(f"IK无解: ({x_cm:.1f}, {y_cm:.1f}, {z_cm:.1f})")
            return None

    def detect_apriltag(self, frame, tag_size=0.051):
        """检测AprilTag"""
        import cv2.aruco as aruco

        detections = []
        dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
        corners, ids, rejected = aruco.detectMarkers(frame, dictionary)

        if ids is None or len(ids) == 0:
            return detections

        half_size = tag_size / 2
        objp = np.array([
            [-half_size, -half_size, 0],
            [ half_size, -half_size, 0],
            [ half_size,  half_size, 0],
            [-half_size,  half_size, 0]
        ], dtype=np.float32)

        for i, tag_id in enumerate(ids):
            corner = corners[i]
            success, rvec, tvec = cv2.solvePnP(objp, corner, self.camera_matrix, self.dist_coeffs)
            if success:
                cam_coords = tvec.flatten()

                # 转换到机器人坐标
                robot_x = self.cam_pos[0] + cam_coords[0]
                robot_y = self.cam_pos[1] - cam_coords[1]
                robot_z = cam_coords[2] - self.cam_pos[2]
                robot_coords = np.array([robot_x, robot_y, robot_z])

                detections.append({
                    'id': int(tag_id[0]),
                    'center': (int(np.mean(corner[0, :, 0])), int(np.mean(corner[0, :, 1]))),
                    'cam_coords': cam_coords,
                    'robot_coords': robot_coords,
                    'grasp_pos': np.array([robot_x, robot_y, self.grasp_height])
                })

                aruco.drawDetectedMarkers(frame, [corner], np.array([[tag_id]]))

        return detections

    def set_initial_position(self):
        """移动到初始位置"""
        if self.arm:
            self.arm.Arm_serial_servo_write6(
                self.initial_pos[0], self.initial_pos[1], self.initial_pos[2],
                self.initial_pos[3], self.initial_pos[4], self.initial_pos[5], 1000
            )
            print(f"移动到初始位置: {self.initial_pos}")

    def move_to_position(self, position, servo5_angle=None, servo6_angle=65):
        """移动到指定位置

        Args:
            position: 目标3D位置(米)
            servo5_angle: servo5角度
            servo6_angle: 夹爪角度,默认65(打开状态)
        """
        angles = self.solve_ik(position)
        if angles is None:
            print(f"无法到达位置: {position}")
            return False

        servo4 = angles[3]
        servo5 = servo5_angle if servo5_angle else angles[4]

        if self.arm:
            self.arm.Arm_serial_servo_write6(
                angles[0], angles[1], angles[2],
                servo4, servo5, servo6_angle, 1000
            )
            print(f"移动到 {position}: [{angles[0]:.1f}, {angles[1]:.1f}, {angles[2]:.1f}, {servo4}, {servo5}, {servo6_angle}]")
            return True
        return False

    def open_gripper(self):
        """打开夹爪"""
        if self.arm:
            self.arm.Arm_serial_servo_write(6, 65, 500)
            print("打开夹爪")

    def close_gripper(self):
        """关闭夹爪"""
        if self.arm:
            self.arm.Arm_serial_servo_write(6, 140, 500)
            print("关闭夹爪")

    def grasp_sequence(self, grasp_pos, place_pos):
        """执行完整的抓取序列"""
        print("\n===== 开始抓取序列 =====")

        # 1. 移动到初始位置 (夹爪打开)
        print("1. 移动到初始位置")
        self.set_initial_position()
        time.sleep(1.5)

        # 2. 移动到目标物体上方 (夹爪打开)
        above_pos = (grasp_pos[0], grasp_pos[1], grasp_pos[2] + 0.05)
        print(f"2. 移动到物体上方 {above_pos}")
        self.move_to_position(above_pos, servo6_angle=65)
        time.sleep(1.5)

        # 3. 下降到抓取高度 (夹爪打开)
        print(f"3. 下降到抓取位置 {grasp_pos}")
        self.move_to_position(grasp_pos, servo6_angle=65)
        time.sleep(1.5)

        # 4. 关闭夹爪抓取
        print("4. 抓取物体")
        self.close_gripper()
        time.sleep(1.0)

        # 5. 抬起 (夹爪保持闭合)
        print("5. 抬起")
        self.move_to_position(above_pos, servo6_angle=140)
        time.sleep(1.5)

        # 6. 移动到放置位置上方 (夹爪保持闭合)
        above_place = (place_pos[0] / 100, place_pos[1] / 100, place_pos[2] / 100 + 0.05)
        print(f"6. 移动到放置位置上方 {above_place}")
        self.move_to_position(above_place, servo6_angle=140)
        time.sleep(1.5)

        # 7. 下降到放置位置 (夹爪保持闭合)
        place_pos_m = (place_pos[0] / 100, place_pos[1] / 100, place_pos[2] / 100)
        print(f"7. 下降到放置位置 {place_pos_m}")
        self.move_to_position(place_pos_m, servo6_angle=140)
        time.sleep(1.5)

        # 8. 打开夹爪放置
        print("8. 放置物体")
        self.open_gripper()
        time.sleep(1.0)

        # 9. 抬起 (夹爪打开)
        print("9. 抬起")
        self.move_to_position(above_place, servo6_angle=65)
        time.sleep(1.5)

        # 10. 返回初始位置 (夹爪打开)
        print("10. 返回初始位置")
        self.set_initial_position()

        print("\n===== 抓取序列完成 =====")

    def run(self):
        """运行测试"""
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("\n===== 抓取测试 (使用ik.py) =====")
        print("按 'd' 检测AprilTag并输出IK解算")
        print("按 'g' 执行抓取")
        print("按 's' 执行完整抓取序列")
        print("按 'q' 退出\n")

        clicked_point = None

        def mouse_callback(event, x, y, flags, param):
            nonlocal clicked_point
            if event == cv2.EVENT_LBUTTONDOWN:
                clicked_point = (x, y)

        cv2.namedWindow('Grasp Test')
        cv2.setMouseCallback('Grasp Test', mouse_callback)

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                display = frame.copy()

                # 检测AprilTag
                tag_detections = self.detect_apriltag(display)

                # 显示信息
                cv2.putText(display, f"AprilTag: {len(tag_detections)}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(display, "d: detect | g: grasp | q: quit", (10, 460),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                if clicked_point:
                    cv2.circle(display, clicked_point, 5, (0, 0, 255), -1)

                cv2.imshow('Grasp Test', display)

                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break
                elif key == ord('d'):
                    for det in tag_detections:
                        print(f"\nID: {det['id']}")
                        print(f"  相机坐标: {[f'{c:.3f}' for c in det['cam_coords']]}")
                        print(f"  基座坐标: {[f'{c:.3f}' for c in det['robot_coords']]}")
                        print(f"  夹取坐标: {[f'{c:.3f}' for c in det['grasp_pos']]}")

                        angles = self.solve_ik(det['grasp_pos'])
                        if angles:
                            print(f"  IK角度: {[f'{a:.1f}' for a in angles]}")

                elif key == ord('g'):
                    if tag_detections:
                        det = tag_detections[0]
                        angles = self.solve_ik(det['grasp_pos'])
                        print(f"  IK角度: {angles}")
                        if angles and self.arm:
                            servo4 = angles[3]
                            servo5 = angles[4]
                            print(f"执行移动: [{angles[0]}, {angles[1]}, {angles[2]}, {servo4}, {servo5}]")
                            self.arm.Arm_serial_servo_write6(
                                angles[0], angles[1], angles[2],
                                servo4, servo5, 90, 1000
                            )
                        elif angles and not self.arm:
                            print("机械臂未连接")
                        else:
                            print("IK无解")

                elif key == ord('s'):
                    if tag_detections:
                        det = tag_detections[0]
                        grasp_pos = det['grasp_pos']
                        place_pos = self.place_pos
                        self.grasp_sequence(grasp_pos, place_pos)
                    else:
                        print("未检测到AprilTag")

        finally:
            cap.release()
            cv2.destroyAllWindows()


if __name__ == '__main__':
    tester = GraspingTester()
    tester.run()