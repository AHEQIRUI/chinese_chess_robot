#!/usr/bin/env python3
"""
中国象棋棋子识别模块
使用camera_fen_project的ChessboardDetector检测棋子
"""

import cv2
import numpy as np
import sys

# 添加camera_fen_project路径 (xq_ws/camera_fen_project)
xq_src_dir = __file__.rsplit('/', 1)[0]
sys.path.insert(0, xq_src_dir + '/camera_fen_project')

# 导入棋盘检测器获取标定数据
from board_detector import BoardDetector
from xiangqi_game import XiangqiBoard

try:
    from core.chessboard_detector import ChessboardDetector
except ImportError:
    ChessboardDetector = None
    print("警告: 无法导入ChessboardDetector，FEN检测不可用")


# BGR颜色用于显示
COLOR_BGR = {
    'red': (0, 0, 255),
    'black': (80, 80, 80),
    'unknown': (255, 255, 255)
}


class PieceDetector:
    """中国象棋棋子检测器 - camera_fen_project版本"""

    def __init__(self, model_path='xq.pt', board_detector=None):
        """
        初始化棋子检测器

        Args:
            model_path: YOLO模型路径(保留参数,已废弃)
            board_detector: 棋盘检测器(用于坐标映射)
        """
        self.board_detector = board_detector or BoardDetector()
        self.mapper = self.board_detector.mapper

        # 初始化FEN检测器
        if ChessboardDetector is None:
            raise RuntimeError("无法导入ChessboardDetector")

        xq_ws_dir = __file__.rsplit('/', 1)[0]
        pose_model_path = xq_ws_dir + '/camera_fen_project/onnx/pose/4_v6-0301.onnx'
        full_classifier_model_path = xq_ws_dir + '/camera_fen_project/onnx/layout_recognition/nano_v3-0319.onnx'

        self.fen_detector = ChessboardDetector(
            pose_model_path=pose_model_path,
            full_classifier_model_path=full_classifier_model_path
        )
        print("FEN检测器已加载 (camera_fen_project)")

    def detect_pieces(self, frame):
        """
        使用camera_fen_project检测棋盘上所有棋子

        Args:
            frame: 输入图像帧(BGR格式)

        Returns:
            pieces: 棋子列表,每项包含:
                   - position: (col, row) 棋盘坐标
                   - color: 'red' 或 'black'
                   - type: 棋子类型中文名
                   - piece_id: 棋子ID字符串
                   - center: (x, y) 像素坐标
                   - confidence: 检测置信度
        """
        # 转换为RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 使用ChessboardDetector检测
        _, _, cells_labels, scores, _ = self.fen_detector.pred_detect_board_and_classifier(frame_rgb)

        if not cells_labels or len(cells_labels) == 0:
            return []

        # 获取棋盘交叉点用于真实像素坐标
        intersections, _, _ = self.board_detector.detect_board(frame)

        # 转换为内部棋子格式
        pieces = self._cells_to_pieces(cells_labels, scores, intersections)

        return pieces

    def _cells_to_pieces(self, cells_labels, scores, intersections=None):
        """
        将camera_fen_project的10x9棋子矩阵转换为内部棋子格式

        Args:
            cells_labels: 10行9列的棋子标签矩阵
            scores: 10行9列的置信度矩阵
            intersections: 棋盘交叉点列表(真实像素坐标)

        Returns:
            pieces: 内部棋子列表格式
        """
        # FEN标签到内部piece_id的映射
        FEN_TO_PIECE = {
            'K': 'RED_K', 'A': 'RED_A', 'B': 'RED_E', 'R': 'RED_R', 'N': 'RED_H', 'C': 'RED_C', 'P': 'RED_P',
            'k': 'BLACK_K', 'a': 'BLACK_A', 'b': 'BLACK_E', 'r': 'BLACK_R', 'n': 'BLACK_H', 'c': 'BLACK_C', 'p': 'BLACK_P',
        }

        FEN_TO_TYPE = {
            'K': '将', 'A': '仕', 'B': '象', 'R': '车', 'N': '马', 'C': '炮', 'P': '兵',
            'k': '帅', 'a': '士', 'b': '相', 'r': '车', 'n': '马', 'c': '炮', 'p': '卒',
        }

        pieces = []
        for row in range(10):
            for col in range(9):
                label = cells_labels[row][col]
                if label in FEN_TO_PIECE:
                    piece_id = FEN_TO_PIECE[label]
                    is_red = piece_id.startswith('RED_')
                    color = 'red' if is_red else 'black'

                    # 使用棋盘交叉点的真实像素坐标
                    if intersections and row < len(intersections) and col < len(intersections[row]):
                        cx, cy = intersections[row][col]
                    else:
                        # 备用计算(仅用于调试)
                        cell_w = 50
                        cx = col * cell_w + cell_w // 2
                        cy = (9 - row) * cell_w + cell_w // 2

                    pieces.append({
                        'position': (col, row),  # 与board_detector一致: row 0=红方底线, row 9=黑方底线
                        'color': color,
                        'type': FEN_TO_TYPE.get(label, '?'),
                        'piece_id': piece_id,
                        'center': (cx, cy),
                        'confidence': scores[row][col]
                    })
        return pieces

    def detect_pieces_with_manual_corners(self, frame, corners):
        """
        使用手动标定的四角检测棋子(备用方案)

        Args:
            frame: 输入图像帧
            corners: 四角坐标 [(左上), (右上), (右下), (左下)]

        Returns:
            pieces: 棋子列表
        """
        # 使用FEN检测器(会自动处理棋盘)
        return self.detect_pieces(frame)

    def classify_pieces_by_color(self, pieces, player_color):
        """
        按颜色分类棋子,区分我方和敌方

        Args:
            pieces: 棋子列表
            player_color: 玩家控制方的颜色 ('red' 或 'black')

        Returns:
            my_pieces: 我方棋子列表
            enemy_pieces: 敌方棋子列表
        """
        my_pieces = []
        enemy_pieces = []

        for piece in pieces:
            if piece['color'] == player_color:
                my_pieces.append(piece)
            else:
                enemy_pieces.append(piece)

        return my_pieces, enemy_pieces

    def pieces_to_fen(self, pieces):
        """
        将检测到的棋子列表转换为FEN格式

        Args:
            pieces: 检测到的棋子列表

        Returns:
            str: FEN格式字符串
        """
        board = XiangqiBoard()
        board.update_from_detection(pieces)
        return board.to_fen()

    def pieces_to_fen_standard(self, pieces):
        """
        将检测到的棋子列表转换为标准FEN格式 (xiangqi.py/chessdb.cn格式)

        Args:
            pieces: 检测到的棋子列表

        Returns:
            str: FEN格式字符串 (黑方视角,与xiangqi.py一致)
        """
        board = XiangqiBoard()
        board.update_from_detection(pieces)
        return board.to_fen()

    def pieces_to_position(self, pieces):
        """
        将检测到的棋子列表转换为 xiangqi.Position 对象

        Args:
            pieces: 检测到的棋子列表

        Returns:
            Position: xiangqi.Position 对象 (用于AI查询)
        """
        from xiangqi import Position

        board = XiangqiBoard()
        board.update_from_detection(pieces)
        fen = board.to_fen()

        # 从标准FEN重建Position
        fen_rows = fen.split()[0].split('/')
        board_str = ''
        for row in fen_rows:
            for ch in row:
                if ch.isdigit():
                    board_str += '.' * int(ch)
                else:
                    board_str += ch
            board_str += '\n'

        return Position(board_str, 0)

    def draw_pieces(self, frame, pieces):
        """在图像上绘制检测到的棋子"""
        display = frame.copy()

        for piece in pieces:
            cx, cy = piece['center']
            bgr = (0, 0, 255) if piece['color'] == 'red' else (0, 0, 0)
            col, row = piece['position']

            col_letter = chr(ord('a') + col)
            row_display = 9 - row

            type_map = {'将': 'K', '帅': 'k', '车': 'R', '马': 'N', '炮': 'C',
                        '兵': 'P', '卒': 'p', '仕': 'A', '士': 'a', '象': 'B', '相': 'b'}
            abbr = type_map.get(piece['type'], '?')

            label = f"{abbr}{col_letter}{row_display}"
            cv2.putText(display, label, (cx - 15, cy + 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr, 1)

        return display


def test():
    """测试棋子检测"""
    if ChessboardDetector is None:
        print("错误: 需要安装 camera_fen_project 依赖")
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    board_detector = BoardDetector()
    show_details = True
    piece_detector = PieceDetector(board_detector=board_detector)
    last_pieces = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 去畸变
        undistorted = board_detector._undistort(frame)

        display = undistorted.copy()

        # 绘制上次检测到的棋子
        if last_pieces:
            display = piece_detector.draw_pieces(display, last_pieces)

            # 统计信息
            red_count = sum(1 for p in last_pieces if p['color'] == 'red')
            black_count = sum(1 for p in last_pieces if p['color'] == 'black')
            status = f"红: {red_count}, 黑: {black_count} | 检测到 {len(last_pieces)} 个棋子"
            cv2.putText(display, status, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            if show_details:
                detail_y = 60
                for piece in last_pieces[:10]:
                    col, row = piece['position']
                    col_letter = chr(ord('a') + col)
                    row_display = 9 - row
                    detail = f"  {piece['type']}{col_letter}{row_display} conf={piece['confidence']:.2f}"
                    cv2.putText(display, detail, (10, detail_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
                    detail_y += 18
        else:
            cv2.putText(display, "按 's' 检测棋子", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.imshow('Piece Detector Test', display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # 检测棋子(使用原始图像)
            pieces = piece_detector.detect_pieces(frame)
            last_pieces = pieces

            # 输出到终端
            if pieces:
                print(f"\n检测到 {len(pieces)} 个棋子:")
                for piece in pieces:
                    col, row = piece['position']
                    col_letter = chr(ord('a') + col)
                    row_display = 9 - row
                    print(f"  {piece['type']}{col_letter}{row_display} ({piece['color']}) conf={piece['confidence']:.2f}")

                fen = piece_detector.pieces_to_fen(pieces)
                print(f"FEN: {fen}")
            else:
                print("\n未检测到棋子")
        elif key == ord('d'):
            show_details = not show_details

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    test()