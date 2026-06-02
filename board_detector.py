 #!/usr/bin/env python3
"""
中国象棋棋盘检测模块
检测9列×10行的棋盘交叉点坐标
"""

import cv2
import numpy as np
import json

def _path_exists(path):
    try:
        with open(path): return True
    except: return False

def _makedirs(path):
    import os as _os
    _os.makedirs(path, exist_ok=True)

# 导入坐标映射器
from board_to_robot import BoardToRobotMapper


class BoardDetector:
    """中国象棋棋盘检测器"""

    def __init__(self, board_width=9, board_height=10, config_path=None):
        self.board_width = board_width  # 9列
        self.board_height = board_height  # 10行
        # 稳定的交叉点(用于平滑)
        self._stable_intersections = None
        self._stable_corners = None
        # 连续稳定帧数阈值
        self._stable_frames = 0
        self._min_stable_frames = 3

        # 读取相机内参用于去畸变
        if config_path is None:
            config_path = 'config/camera_config.json'

        if _path_exists(config_path):
            with open(config_path, 'r') as f:
                calib = json.load(f)
                self.camera_matrix = np.array(calib['camera_matrix'])
                self.dist_coeffs = np.array(calib['dist_coeffs'])
        else:
            self.camera_matrix = np.array([
                [946.82, 0, 416.11],
                [0, 946.37, 259.55],
                [0, 0, 1]
            ])
            self.dist_coeffs = np.array([[-0.51, 0.75, -0.002, -0.003, -1.12]])

        # 尝试加载之前保存的棋盘标定数据
        calib_board_path = 'config/board_calibration.json'
        if _path_exists(calib_board_path):
            with open(calib_board_path, 'r') as f:
                calib_board = json.load(f)
                self._saved_corners = [tuple(c) for c in calib_board['corners']]
                self._saved_intersections = calib_board.get('intersections')
                print(f"已加载棋盘标定数据: {len(self._saved_corners)} 个角点")
        else:
            self._saved_corners = None
            self._saved_intersections = None

        # 初始化坐标映射器
        self.mapper = BoardToRobotMapper()

        # 去畸变缓存
        self._undistort_cache = {}

    def _undistort(self, frame):
        """对图像去畸变"""
        h, w = frame.shape[:2]
        new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
        )
        undistorted = cv2.undistort(frame, self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)
        return undistorted

    def detect_board(self, frame):
        """
        检测棋盘并返回交叉点坐标

        Args:
            frame: 输入图像帧

        Returns:
            intersections: 90个交叉点坐标列表
            homography: 单应性矩阵(可用于透视矫正)
            board_corners: 棋盘四角的像素坐标
        """
        # 如果有已保存的标定数据,直接使用
        if self._saved_corners and len(self._saved_corners) == 4:
            intersections = self.compute_grid_from_corners(self._saved_corners)
            return intersections, None, np.array(self._saved_corners, dtype=np.float32)

        # 去畸变
        undistorted_frame = self._undistort(frame)
        gray = cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2GRAY)

        # 高斯模糊去噪
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 自适应阈值二值化
        binary = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # 形态学操作去噪
        kernel = np.ones((3, 3), np.uint8)
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 边缘检测
        edges = cv2.Canny(morph, 50, 150, apertureSize=3)

        # 直线检测
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=100,
            maxLineGap=10
        )

        if lines is None or len(lines) == 0:
            return None, None, None

        # 分类横线和竖线
        horizontal_lines = []
        vertical_lines = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            if angle < 10 or angle > 170:
                horizontal_lines.append(line[0])
            elif 80 < angle < 100:
                vertical_lines.append(line[0])

        if len(horizontal_lines) < 9 or len(vertical_lines) < 8:
            return None, None, None

        # 聚类横线(按y坐标排序,去重)
        horizontal_lines = self._cluster_lines(horizontal_lines, axis='y')
        # 聚类竖线(按x坐标排序,去重)
        vertical_lines = self._cluster_lines(vertical_lines, axis='x')

        # 取最外层的线作为边界
        horizontal_lines = sorted(horizontal_lines, key=lambda l: l[1])[:10]
        vertical_lines = sorted(vertical_lines, key=lambda l: l[0])[:9]

        # 计算交叉点
        intersections = []
        for h_line in horizontal_lines:
            row_points = []
            for v_line in vertical_lines:
                px, py = self._line_intersection(h_line, v_line)
                if px is not None and py is not None:
                    row_points.append((int(px), int(py)))
            if len(row_points) >= 9:
                intersections.append(row_points[:9])

        if len(intersections) < 10:
            return None, None, None

        # 提取棋盘四角(用于标定)
        top_left = intersections[0][0]
        top_right = intersections[0][-1]
        bottom_left = intersections[-1][0]
        bottom_right = intersections[-1][-1]

        board_corners = np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)

        # 检查稳定性 - 只有连续多帧检测到相似的点才更新稳定结果
        if self._stable_intersections is None:
            self._stable_intersections = intersections
            self._stable_corners = board_corners
            self._stable_frames = 1
        else:
            # 检查与稳定结果的相似度
            if self._is_similar(intersections, self._stable_intersections):
                self._stable_frames += 1
                if self._stable_frames >= self._min_stable_frames:
                    # 更新稳定结果
                    self._stable_intersections = intersections
                    self._stable_corners = board_corners
            else:
                # 不相似,重置计数
                self._stable_frames = 1

        return self._stable_intersections, None, self._stable_corners

    def _is_similar(self, new_inters, stable_inters, threshold=5.0):
        """检查两组交叉点是否相似(允许小幅抖动)"""
        if new_inters is None or stable_inters is None:
            return False
        if len(new_inters) != len(stable_inters):
            return False

        total_diff = 0
        count = 0

        for row_idx, row in enumerate(new_inters):
            for col_idx, (px, py) in enumerate(row):
                if row_idx < len(stable_inters) and col_idx < len(stable_inters[row_idx]):
                    sx, sy = stable_inters[row_idx][col_idx]
                    diff = np.sqrt((px - sx)**2 + (py - sy)**2)
                    total_diff += diff
                    count += 1

        if count == 0:
            return False

        avg_diff = total_diff / count
        return avg_diff < threshold

    def reset_stability(self):
        """重置稳定状态"""
        self._stable_intersections = None
        self._stable_corners = None
        self._stable_frames = 0

    def _cluster_lines(self, lines, axis='y'):
        """对直线进行聚类,去除重复线"""
        if len(lines) == 0:
            return []

        # lines现在是简单的[x1,y1,x2,y2]列表
        if axis == 'y':
            lines = sorted(lines, key=lambda l: min(l[1], l[3]))
        else:
            lines = sorted(lines, key=lambda l: min(l[0], l[2]))

        clustered = []
        threshold = 20

        for line in lines:
            coord = line[1] if axis == 'y' else line[0]

            is_duplicate = False
            for cx in clustered:
                c_coord = cx[1] if axis == 'y' else cx[0]
                if abs(coord - c_coord) < threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                clustered.append(line)

        return clustered

    def _line_intersection(self, line1, line2):
        """计算两条直线的交点"""
        x1, y1, x2, y2 = line1
        x3, y3, x4, y4 = line2

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6:
            return None, None

        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom

        return px, py

    def draw_board(self, frame, intersections):
        """在图像上绘制检测到的棋盘线"""
        display = frame.copy()

        if intersections is None:
            return display

        # 绘制所有检测到的交叉点
        for row_idx, row in enumerate(intersections):
            for col_idx, (px, py) in enumerate(row):
                # 从对面视角显示坐标: (0,9)->a0, (8,0)->i9
                # row_display = 9 - row_idx (上下翻转)
                col_letter = chr(ord('a') + col_idx)
                row_display = 9 - row_idx
                coord_str = f"{col_letter}{row_display}"

                # 交叉点圆圈
                cv2.circle(display, (px, py), 3, (0, 255, 0), -1)
                # 标注坐标 - 同时显示 (col,row) 和 a0 格式
                numeric_str = f"({col_idx},{row_idx})"
                cv2.putText(display, coord_str,
                          (px + 5, py - 12),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
                cv2.putText(display, numeric_str,
                          (px + 5, py + 3),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.25, (255, 255, 0), 1)

        return display

    def get_grid_position(self, intersections, col, row):
        """
        根据棋盘坐标(col, row)获取像素坐标

        Args:
            intersections: detect_board返回的交叉点列表
            col: 列索引(0-8)
            row: 行索引(0-9)

        Returns:
            (x, y): 像素坐标,若无效返回None
        """
        if intersections is None:
            return None
        if row < 0 or row >= len(intersections):
            return None
        if col < 0 or col >= len(intersections[0]):
            return None
        return intersections[row][col]

    def compute_grid_from_corners(self, corners):
        """
        根据四角坐标计算9x10网格的所有交叉点

        Args:
            corners: 四角坐标 [(左上), (右上), (右下), (左下)]

        Returns:
            intersections: 90个交叉点列表
        """
        if len(corners) != 4:
            return None

        top_left, top_right, bottom_right, bottom_left = corners

        intersections = []

        for row in range(10):
            row_points = []
            for col in range(9):
                # 线性插值计算每个交叉点
                # 行方向插值 (从上到下)
                t_row = row / 9.0
                # 列方向插值 (从左到右)
                t_col = col / 8.0

                # 上边插值
                top_x = top_left[0] + t_col * (top_right[0] - top_left[0])
                top_y = top_left[1] + t_col * (top_right[1] - top_left[1])

                # 下边插值
                bottom_x = bottom_left[0] + t_col * (bottom_right[0] - bottom_left[0])
                bottom_y = bottom_left[1] + t_col * (bottom_right[1] - bottom_left[1])

                # 在上下边之间插值
                px = top_x + t_row * (bottom_x - top_x)
                py = top_y + t_row * (bottom_y - top_y)

                row_points.append((int(px), int(py)))

            intersections.append(row_points)

        return intersections

    def intersections_to_robot_coords(self, intersections, z_height=5.0):
        """
        将棋盘交叉点转换为机械臂坐标

        Args:
            intersections: 棋盘交叉点列表
            z_height: Z轴高度(厘米)

        Returns:
            robot_coords: 机械臂坐标列表 [x, y, z] (厘米)
        """
        if intersections is None:
            return None

        robot_coords = []
        for row_idx in range(len(intersections)):
            row_coords = []
            for col_idx in range(len(intersections[0])):
                pos = self.mapper.board_to_robot(col_idx, row_idx, z_height)
                row_coords.append(pos.tolist())
            robot_coords.append(row_coords)

        return robot_coords

    def save_robot_coordinates(self, intersections, z_height=5.0, path='config/board_robot_coords.json'):
        """
        保存交叉点的机械臂坐标到文件

        Args:
            intersections: 棋盘交叉点列表
            z_height: Z轴高度(厘米)
            path: 保存路径
        """
        robot_coords = self.intersections_to_robot_coords(intersections, z_height)

        if robot_coords is None:
            print("错误: 无交叉点数据")
            return False

        data = {
            'z_height': z_height,
            'grid_size_col_cm': self.mapper.GRID_SIZE_COL_CM,
            'grid_size_row_cm': self.mapper.GRID_SIZE_ROW_CM,
            'river_gap_cm': self.mapper.RIVER_GAP_CM,
            'board_origin': self.mapper.board_origin_robot.tolist(),
            'board_dir_x': self.mapper.board_dir_x.tolist(),
            'board_dir_y': self.mapper.board_dir_y.tolist(),
            'robot_coords': robot_coords
        }

        import os as _os
        _os.makedirs(path, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"机械臂坐标已保存: {path}")
        return True

    def print_robot_coordinates(self, intersections, z_height=5.0):
        """打印所有交叉点的机械臂坐标"""
        robot_coords = self.intersections_to_robot_coords(intersections, z_height)

        if robot_coords is None:
            return

        print("\n" + "=" * 60)
        print(f"棋盘交叉点机械臂坐标 (Z={z_height}cm)")
        print("=" * 60)
        print(f"{'Row':>3} {'Col':>3} {'X':>7} {'Y':>7} {'Z':>7}")
        print("-" * 40)

        for row_idx, row in enumerate(robot_coords):
            for col_idx, coord in enumerate(row):
                print(f"{row_idx:>3} {col_idx:>3} {coord[0]:>7.1f} {coord[1]:>7.1f} {coord[2]:>7.1f}")


def test():
    """测试棋盘检测,支持鼠标选择四角"""
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    detector = BoardDetector()

    print("按 'q' 退出测试")
    print("按 's' 保存当前帧到 calibration_data/")
    print("按 'm' 手动选择棋盘四角")
    print("按 'r' 重置四角选择")
    print("按 'c' 保存标定数据")
    print("按 'p' 打印并保存机械臂坐标")
    print("按 'p' 打印机械臂坐标")

    _makedirs('calibration_data')
    save_idx = 0

    # 手动选择四角状态
    manual_corners = []  # 手动选择的四角 [(x,y), ...]
    manual_intersections = None  # 根据四角计算的网格
    is_selecting = False

    def mouse_callback(event, x, y, flags, param):
        nonlocal manual_corners, is_selecting, manual_intersections
        if event == cv2.EVENT_LBUTTONDOWN:
            if is_selecting:
                manual_corners.append((x, y))
                print(f"选择第{len(manual_corners)}个角: ({x}, {y})")
                if len(manual_corners) >= 4:
                    is_selecting = False
                    # 根据四角计算网格
                    manual_intersections = detector.compute_grid_from_corners(manual_corners)
                    print("四角选择完成!已计算网格交叉点")
                    print(f"保存标定请按 'c'")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 获取去畸变后的图像用于显示
        undistorted_frame = detector._undistort(frame)

        intersections, _, corners = detector.detect_board(frame)

        # 如果有手动选择的四角,优先显示手动计算的网格
        display_intersections = manual_intersections if manual_intersections else intersections
        display = detector.draw_board(undistorted_frame, display_intersections)

        # 显示四角标定参考点
        if corners is not None and manual_intersections is None:
            for i, pt in enumerate(corners):
                cv2.circle(display, tuple(map(int, pt)), 5, (0, 0, 255), -1)
                cv2.putText(display, f"corner{i}", tuple(map(int, pt)),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # 绘制手动选择的四角
        if manual_corners:
            for i, (cx, cy) in enumerate(manual_corners):
                cv2.circle(display, (cx, cy), 8, (255, 0, 0), -1)
                cv2.putText(display, f"点{i+1}", (cx + 10, cy - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                if i > 0:
                    cv2.line(display, manual_corners[i-1], (cx, cy), (255, 0, 0), 2)
            if len(manual_corners) == 4:
                # 闭合四边形
                cv2.line(display, manual_corners[3], manual_corners[0], (255, 0, 0), 2)

        status = f"检测: {'OK' if display_intersections else 'FAIL'}"
        if is_selecting:
            status += f" | 手动选择: {len(manual_corners)}/4"
        elif manual_intersections:
            status += " | 手动标定"
        cv2.putText(display, status, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 操作提示
        mode_text = "m:选角 | r:重置 | s:保存 | c:标定 | p:坐标" if not is_selecting else "点击选择四角..."
        cv2.putText(display, mode_text, (10, 460),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        cv2.imshow('Board Detector Test', display)
        cv2.setMouseCallback('Board Detector Test', mouse_callback)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f'calibration_data/board_{save_idx}.jpg'
            cv2.imwrite(filename, frame)
            print(f"保存: {filename}")
            save_idx += 1
        elif key == ord('m'):
            manual_corners = []
            manual_intersections = None
            is_selecting = True
            print("开始手动选择四角,请依次点击: 左上→右上→右下→左下")
        elif key == ord('r'):
            manual_corners = []
            manual_intersections = None
            is_selecting = False
            detector.reset_stability()
            print("已重置四角选择")
        elif key == ord('c'):
            if manual_intersections and len(manual_corners) == 4:
                # 保存标定数据
                import json
                calib_data = {
                    'corners': [list(c) for c in manual_corners],
                    'intersections': [[list(p) for p in row] for row in manual_intersections],
                    'grid_size_cm': 2.8
                }
                calib_path = 'config/board_calibration.json'
                with open(calib_path, 'w') as f:
                    json.dump(calib_data, f, indent=2)
                print(f"标定数据已保存: {calib_path}")
            else:
                print("请先选择四角")
        elif key == ord('p'):
            if display_intersections:
                detector.print_robot_coordinates(display_intersections)
                detector.save_robot_coordinates(display_intersections)
            else:
                print("无可用交叉点数据")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    test()