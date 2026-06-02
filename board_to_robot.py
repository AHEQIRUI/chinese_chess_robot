#!/usr/bin/env python3
"""
棋盘坐标转机器人坐标模块
将棋盘位置(col, row)转换为机器人工作空间坐标(厘米)
"""

import numpy as np
import json

def _path_exists(path):
    try:
        with open(path): return True
    except: return False


class BoardToRobotMapper:
    """棋盘坐标到机器人坐标的映射器"""

    # 棋盘格子宽度(单位:厘米)
    GRID_SIZE_COL_CM = 3.1  # 列间距 3.1cm
    GRID_SIZE_ROW_CM = 2.85  # 行间距 2.8cm
    RIVER_GAP_CM = 2.2  # 楚河汉界间隔(厘米)

    def __init__(self, config_path=None):
        """
        初始化映射器

        Args:
            config_path: 配置文件路径,包含棋盘标定参数
        """
        # 读取相机内参(复用现有标定)
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

        # 相机位置(来自test_grasp_yolo.py, 转换为厘米)
        self.cam_pos = np.array([0.0, 14.0, 68.0])  # x, y, z (厘米)
        # 抓取高度(厘米)
        self.grasp_height = 10  # 2cm

        # 棋盘标定参数(厘米)
        # 棋盘左上角(col=0,row=0)在机器人坐标系中的位置
        self.board_origin_robot = np.array([-12.4, 28, 2.0])  # x, y, z (厘米)
        # 棋盘X方向(col增加)对应机器人X轴
        self.board_dir_x = np.array([1, 0, 0])  # col增加 -> robot X增加
        # 棋盘Y方向(row增加)对应机器人Y轴(向下为正)
        self.board_dir_y = np.array([0, 1, 0])  # row增加 -> robot Y减小(棋盘上方Y值大)

        # 棋盘尺寸(9列×10行)
        self.board_cols = 9
        self.board_rows = 10

    def set_board_calibration(self, origin, dir_x, dir_y, grid_size_cm):
        """
        设置棋盘标定参数

        Args:
            origin: 棋盘左上角在机器人坐标系中的位置 [x, y, z] (厘米)
            dir_x: 棋盘列方向的单位向量
            dir_y: 棋盘行方向的单位向量
            grid_size_cm: 格子大小(厘米)
        """
        self.board_origin_robot = np.array(origin)
        self.board_dir_x = np.array(dir_x)
        self.board_dir_y = np.array(dir_y)
        self.GRID_SIZE_CM = grid_size_cm

    def board_to_robot(self, col, row, z_height=8.5, arm_color='red'):
        """
        将棋盘坐标转换为机器人坐标(厘米)

        Args:
            col: 列索引(0-8)
            row: 行索引(0-9)
            z_height: 抓取高度(厘米),默认5cm
            arm_color: 'red' 或 'black' - 当前已不再需要，因为坐标转换已在cloud_query中处理

        Returns:
            robot_pos: [x, y, z] 机器人坐标系中的位置(厘米)
        """
        # X方向: 按列间距计算
        x = self.board_origin_robot[0] + col * self.GRID_SIZE_COL_CM * self.board_dir_x[0]

        # Y方向: 考虑楚河汉界间隔(row 4到row 5之间为2.2cm)
        if row <= 4:
            # 上半区(row 0-4): 正常2.9cm间距
            y_offset = row * self.GRID_SIZE_ROW_CM
        else:
            # 下半区(row 5-9): 需要加上楚河汉界间隔
            y_offset = 4 * self.GRID_SIZE_ROW_CM + self.RIVER_GAP_CM + (row - 5) * self.GRID_SIZE_ROW_CM

        y = self.board_origin_robot[1] - y_offset
        z = z_height  # 保持指定高度

        return np.array([x, y, z])

    def robot_to_board(self, robot_pos):
        """
        将机器人坐标(厘米)转换为棋盘坐标

        Args:
            robot_pos: [x, y, z] 机器人坐标系中的位置(厘米)

        Returns:
            (col, row): 最近的棋盘格坐标
        """
        rel = robot_pos - self.board_origin_robot

        # X方向: 按列间距计算
        col_float = np.dot(rel, self.board_dir_x) / self.GRID_SIZE_COL_CM

        # Y方向: 考虑楚河汉界间隔
        y_dist = -rel[1]  # 因为board_dir_y = -1,所以用-rel
        river_line = 4 * self.GRID_SIZE_ROW_CM + self.RIVER_GAP_CM / 2
        if y_dist < river_line:
            # 上半区
            row_float = y_dist / self.GRID_SIZE_ROW_CM
        else:
            # 下半区
            row_float = 5 + (y_dist - 4 * self.GRID_SIZE_ROW_CM - self.RIVER_GAP_CM) / self.GRID_SIZE_ROW_CM

        col = int(np.clip(round(col_float), 0, self.board_cols - 1))
        row = int(np.clip(round(row_float), 0, self.board_rows - 1))

        return col, row

    def board_to_robot_from_ucci(self, ucci_str, z_height=8.5):
        """
        将UCCI格式坐标转换为机器人坐标

        Args:
            ucci_str: UCCI格式坐标 (如 'a0', 'i9')
            z_height: Z轴高度(厘米)

        Returns:
            list: [x, y, z] 机器人坐标 (厘米)
        """
        col = ord(ucci_str[0].lower()) - ord('a')
        row = int(ucci_str[1])
        return self.board_to_robot(col, row, z_height)

    def pixel_to_board(self, u, v, depth_cm=50.0):
        """
        将像素坐标转换为棋盘坐标

        Args:
            u, v: 像素坐标
            depth_cm: 目标物距相机距离(厘米)

        Returns:
            (col, row): 棋盘坐标
        """
        # 使用相机内参
        pixel_hom = np.array([u, v, 1.0])
        cam_intrinsic_inv = np.linalg.inv(self.camera_matrix)
        cam_coords = cam_intrinsic_inv @ pixel_hom
        cam_offsets = cam_coords[:2] * depth_cm / 1000.0  # 转换为米

        # 相机位置(来自test_grasp_yolo.py)
        cam_pos_m = self.cam_pos / 100.0  # 转换回米用于计算

        robot_x = cam_pos_m[0] + cam_offsets[0]
        robot_y = cam_pos_m[1] - cam_offsets[1]
        robot_z = cam_pos_m[2] - depth_cm / 1000.0

        robot_pos = np.array([robot_x, robot_y, robot_z]) * 100.0  # 转回厘米
        return self.robot_to_board(robot_pos)

    def calibrate_board_from_corners(self, pixel_corners, robot_corners_cm):
        """
        通过四角标定法标定棋盘位置

        Args:
            pixel_corners: 棋盘四角在图像中的像素坐标, [(top_left), (top_right), (bottom_right), (bottom_left)]
            robot_corners_cm: 棋盘四角在机器人坐标系中的位置(厘米), 同样顺序

        Returns:
            标定误差
        """
        # 计算像素坐标中的格子大小
        pt1, pt2, pt3, pt4 = pixel_corners

        # 横向格子宽度(像素)
        grid_w = np.sqrt((pt2[0] - pt1[0])**2 + (pt2[1] - pt1[1])**2) / 8

        # 纵向格子高度(像素)
        grid_h = np.sqrt((pt4[0] - pt1[0])**2 + (pt4[1] - pt1[1])**2) / 9

        self.GRID_SIZE_CM = 3.0  # 默认值,需要根据实际情况调整

        # 更新原点
        self.board_origin_robot = np.array(robot_corners_cm[0])

        # 计算方向向量
        dir_right = (np.array(robot_corners_cm[1]) - np.array(robot_corners_cm[0])) / 8  # 8格到右上角
        dir_down = (np.array(robot_corners_cm[3]) - np.array(robot_corners_cm[0])) / 9  # 9格到左下角

        self.board_dir_x = dir_right / np.linalg.norm(dir_right)
        self.board_dir_y = dir_down / np.linalg.norm(dir_down)

        print(f"棋盘标定完成:")
        print(f"  原点: {self.board_origin_robot} cm")
        print(f"  X方向: {self.board_dir_x}")
        print(f"  Y方向: {self.board_dir_y}")
        print(f"  格子大小: {self.GRID_SIZE_CM} cm")


def test():
    """测试坐标映射"""
    mapper = BoardToRobotMapper()

    print("=" * 60)
    print("棋盘坐标 -> 机器人坐标 (9列×10行 = 90个点)")
    print("=" * 60)
    print(f"{'Col':>3} {'Row':>3} {'Robot X':>8} {'Robot Y':>8} {'Robot Z':>8}")
    print("-" * 60)

    for row in range(10):
        for col in range(9):
            pos = mapper.board_to_robot(col, row, z_height=8.5)
            print(f"{col:>3} {row:>3} {pos[0]:>8.1f} {pos[1]:>8.1f} {pos[2]:>8.1f}")

    print("\n机器人坐标 -> 棋盘坐标 测试")
    print("-" * 60)

    robot_positions = [
        np.array([0.0, 0, 2.0])
    ]

    for pos in robot_positions:
        col, row = mapper.robot_to_board(pos)
        print(f"({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) cm -> ({col}, {row})")


if __name__ == '__main__':
    test()