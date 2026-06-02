#!/usr/bin/env python3
"""
中国象棋游戏状态模块
管理棋盘局面和走棋规则
"""

# 中国象棋棋子编号
PIECE_ID = {
    'RED_K': 0,   # 将
    'RED_A': 1,   # 仕
    'RED_E': 2,   # 象
    'RED_R': 3,   # 车
    'RED_H': 4,   # 马
    'RED_C': 5,   # 炮
    'RED_P': 6,   # 兵
    'BLACK_K': 7,  # 帅
    'BLACK_A': 8,  # 士
    'BLACK_E': 9,  # 相
    'BLACK_R': 10, # 车
    'BLACK_H': 11, # 马
    'BLACK_C': 12, # 炮
    'BLACK_P': 13, # 卒
}

PIECE_NAMES = {
    0: '将', 1: '仕', 2: '象', 3: '车', 4: '马', 5: '炮', 6: '兵',
    7: '帅', 8: '士', 9: '相', 10: '车', 11: '马', 12: '炮', 13: '卒',
}

# FEN格式棋子符号 (标准中国象棋FEN格式)
# 红方大写: R=车, N=马, B=相, A=仕, K=帅, C=炮, P=兵
# 黑方小写: r=车, n=马, b=象, a=士, k=将, c=炮, p=卒
PIECE_FEN = {
    # ID 0-6 是红方棋子,FEN中用大写
    0: 'K', 1: 'A', 2: 'B', 3: 'R', 4: 'N', 5: 'C', 6: 'P',
    # ID 7-13 是黑方棋子,FEN中用小写
    7: 'k', 8: 'a', 9: 'b', 10: 'r', 11: 'n', 12: 'c', 13: 'p',
}

# 红方和黑方的棋子ID
RED_PIECES = [0, 1, 2, 3, 4, 5, 6]
BLACK_PIECES = [7, 8, 9, 10, 11, 12, 13]

# 判断红方棋子
def is_red_piece(piece_id):
    return piece_id in RED_PIECES

# 判断黑方棋子
def is_black_piece(piece_id):
    return piece_id in BLACK_PIECES

# 判断是否为同一方的棋子
def is_same_side(piece_id1, piece_id2):
    return (is_red_piece(piece_id1) and is_red_piece(piece_id2)) or \
           (is_black_piece(piece_id1) and is_black_piece(piece_id2))


class XiangqiBoard:
    """中国象棋棋盘"""

    def __init__(self):
        # 10行 x 9列 的棋盘
        # None表示空位,否则是棋子ID
        self.board = [[None] * 9 for _ in range(10)]
        self.reset_board()

    def reset_board(self):
        """初始化棋盘到标准开局"""
        # 红方 (row 0 = 红方底线)
        self.board[0][4] = PIECE_ID['RED_K']   # 将
        self.board[0][3] = PIECE_ID['RED_A']   # 仕
        self.board[0][5] = PIECE_ID['RED_A']   # 仕
        self.board[0][2] = PIECE_ID['RED_E']   # 象
        self.board[0][6] = PIECE_ID['RED_E']   # 象
        self.board[0][0] = PIECE_ID['RED_R']   # 车
        self.board[0][8] = PIECE_ID['RED_R']   # 车
        self.board[0][1] = PIECE_ID['RED_H']   # 马
        self.board[0][7] = PIECE_ID['RED_H']   # 马
        self.board[2][1] = PIECE_ID['RED_C']   # 炮
        self.board[2][7] = PIECE_ID['RED_C']   # 炮
        self.board[3][0] = PIECE_ID['RED_P']   # 兵
        self.board[3][2] = PIECE_ID['RED_P']
        self.board[3][4] = PIECE_ID['RED_P']
        self.board[3][6] = PIECE_ID['RED_P']
        self.board[3][8] = PIECE_ID['RED_P']

        # 黑方 (row 9 = 黑方底线)
        self.board[9][4] = PIECE_ID['BLACK_K']  # 帅
        self.board[9][3] = PIECE_ID['BLACK_A']   # 士
        self.board[9][5] = PIECE_ID['BLACK_A']   # 士
        self.board[9][2] = PIECE_ID['BLACK_E']   # 相
        self.board[9][6] = PIECE_ID['BLACK_E']   # 相
        self.board[9][0] = PIECE_ID['BLACK_R']   # 车
        self.board[9][8] = PIECE_ID['BLACK_R']   # 车
        self.board[9][1] = PIECE_ID['BLACK_H']   # 马
        self.board[9][7] = PIECE_ID['BLACK_H']   # 马
        self.board[7][1] = PIECE_ID['BLACK_C']   # 炮
        self.board[7][7] = PIECE_ID['BLACK_C']   # 炮
        self.board[6][0] = PIECE_ID['BLACK_P']   # 卒
        self.board[6][2] = PIECE_ID['BLACK_P']
        self.board[6][4] = PIECE_ID['BLACK_P']
        self.board[6][6] = PIECE_ID['BLACK_P']
        self.board[6][8] = PIECE_ID['BLACK_P']

    def get_piece(self, col, row):
        """获取指定位置的棋子"""
        if 0 <= col < 9 and 0 <= row < 10:
            return self.board[row][col]
        return None

    def set_piece(self, col, row, piece_id):
        """设置指定位置的棋子"""
        if 0 <= col < 9 and 0 <= row < 10:
            self.board[row][col] = piece_id

    def remove_piece(self, col, row):
        """移除指定位置的棋子"""
        self.set_piece(col, row, None)

    def move_piece(self, from_col, from_row, to_col, to_row):
        """移动棋子"""
        piece = self.get_piece(from_col, from_row)
        if piece is None:
            return False

        self.set_piece(to_col, to_row, piece)
        self.remove_piece(from_col, from_row)
        return True

    def to_fen(self):
        """
        将当前棋盘转换为FEN格式 (Forsyth-Edwards Notation)

        中国象棋FEN格式说明:
        - 从黑方视角(row 0-9)从上到下书写
        - 每行用'/'分隔,左侧是9列
        - 空位用数字表示连续的空位数(1-9)
        - 红方棋子用大写字母,黑方用小写字母

        Returns:
            str: FEN格式字符串
        """
        fen_rows = []

        # 内部: row 0 = 红方底线, row 9 = 黑方底线
        # FEN: row 0 = 黑方底线, row 9 = 红方底线
        # 所以需要从row 9到row 0输出(反转)
        for row in range(9, -1, -1):
            row_str = ""
            empty_count = 0

            for col in range(9):
                piece = self.board[row][col]

                if piece is None:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    # 标准FEN: 红方大写, 黑方小写
                    fen_char = PIECE_FEN.get(piece, '?')
                    row_str += fen_char

            if empty_count > 0:
                row_str += str(empty_count)
            if row_str == "":
                row_str = "9"
            fen_rows.append(row_str)

        fen = "/".join(fen_rows)
        return fen

    def get_legal_moves(self, col, row):
        """
        获取指定位置棋子的所有合法走法

        Returns:
            list: [(to_col, to_row), ...] 目标位置列表
        """
        piece = self.get_piece(col, row)
        if piece is None:
            return []

        if piece == PIECE_ID['RED_K'] or piece == PIECE_ID['BLACK_K']:
            return self._get_general_moves(col, row, piece)
        elif piece == PIECE_ID['RED_A'] or piece == PIECE_ID['BLACK_A']:
            return self._get_advisor_moves(col, row, piece)
        elif piece == PIECE_ID['RED_E'] or piece == PIECE_ID['BLACK_E']:
            return self._get_elephant_moves(col, row, piece)
        elif piece == PIECE_ID['RED_R'] or piece == PIECE_ID['BLACK_R']:
            return self._get_chariot_moves(col, row, piece)
        elif piece == PIECE_ID['RED_H'] or piece == PIECE_ID['BLACK_H']:
            return self._get_horse_moves(col, row, piece)
        elif piece == PIECE_ID['RED_C'] or piece == PIECE_ID['BLACK_C']:
            return self._get_cannon_moves(col, row, piece)
        elif piece == PIECE_ID['RED_P'] or piece == PIECE_ID['BLACK_P']:
            return self._get_pawn_moves(col, row, piece)

        return []

    def _get_general_moves(self, col, row, piece):
        """将/帅的走法(九宫内移动)"""
        moves = []
        is_red = is_red_piece(piece)

        # 将/帅的活动范围
        if is_red:
            min_row, max_row = 7, 9
        else:
            min_row, max_row = 0, 2

        # 四个方向各走一步
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        for dc, dr in directions:
            new_col, new_row = col + dc, row + dr
            if min_row <= new_row <= max_row and 3 <= new_col <= 5:
                target = self.get_piece(new_col, new_row)
                if target is None or not is_same_side(piece, target):
                    moves.append((new_col, new_row))

        return moves

    def _get_advisor_moves(self, col, row, piece):
        """仕/士的走法(九宫内斜线移动)"""
        moves = []
        is_red = is_red_piece(piece)

        if is_red:
            min_row, max_row = 7, 9
        else:
            min_row, max_row = 0, 2

        # 斜线方向
        directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        for dc, dr in directions:
            new_col, new_row = col + dc, row + dr
            if min_row <= new_row <= max_row and 3 <= new_col <= 5:
                target = self.get_piece(new_col, new_row)
                if target is None or not is_same_side(piece, target):
                    moves.append((new_col, new_row))

        return moves

    def _get_elephant_moves(self, col, row, piece):
        """象/相的走法(田字,不能过河)"""
        moves = []
        is_red = is_red_piece(piece)

        if is_red:
            min_row, max_row = 5, 9
        else:
            min_row, max_row = 0, 4

        # 象眼位置(田字中心)
        eye_positions = [(col + 1, row + 1), (col + 1, row - 1),
                       (col - 1, row + 1), (col - 1, row - 1)]

        # 象的目标位置
        directions = [(2, 2), (2, -2), (-2, 2), (-2, -2)]

        for eye, direc in zip(eye_positions, directions):
            eye_col, eye_row = eye
            new_col, new_row = col + direc[0], row + direc[1]

            # 检查象眼是否有棋子阻挡
            if self.get_piece(eye_col, eye_row) is not None:
                continue

            # 检查目标位置是否在范围内
            if not (min_row <= new_row <= max_row and 0 <= new_col <= 8):
                continue

            # 检查目标位置是否可以走
            target = self.get_piece(new_col, new_row)
            if target is None or not is_same_side(piece, target):
                moves.append((new_col, new_row))

        return moves

    def _get_chariot_moves(self, col, row, piece):
        """车/车的走法(直线,不能越子)"""
        moves = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        for dc, dr in directions:
            new_col, new_row = col + dc, row + dr
            while 0 <= new_col <= 8 and 0 <= new_row <= 9:
                target = self.get_piece(new_col, new_row)
                if target is None:
                    moves.append((new_col, new_row))
                else:
                    if not is_same_side(piece, target):
                        moves.append((new_col, new_row))
                    break
                new_col += dc
                new_row += dr

        return moves

    def _get_horse_moves(self, col, row, piece):
        """马/马的走法(撇脚马)"""
        moves = []

        # 马腿方向和目标方向
        horse_moves = [
            ((1, 0), (2, 1)),   # 右,下下
            ((1, 0), (2, -1)),  # 右,上上
            ((-1, 0), (-2, 1)), # 左,下下
            ((-1, 0), (-2, -1)),# 左,上上
            ((0, 1), (1, 2)),  # 下,右右
            ((0, 1), (-1, 2)), # 下,左左
            ((0, -1), (1, -2)),# 上,右右
            ((0, -1), (-1, -2)),# 上,左左
        ]

        for leg, target in horse_moves:
            leg_col, leg_row = leg
            target_col, target_row = target

            new_leg_col, new_leg_row = col + leg_col, row + leg_row
            new_target_col, new_target_row = col + target_col, row + target_row

            # 检查马腿是否有棋子
            if self.get_piece(new_leg_col, new_leg_row) is not None:
                continue

            # 检查目标是否在棋盘内
            if not (0 <= new_target_col <= 8 and 0 <= new_target_row <= 9):
                continue

            # 检查目标是否可以走
            target_piece = self.get_piece(new_target_col, new_target_row)
            if target_piece is None or not is_same_side(piece, target_piece):
                moves.append((new_target_col, new_target_row))

        return moves

    def _get_cannon_moves(self, col, row, piece):
        """炮/炮的走法(直线,吃子需隔一子)"""
        moves = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        for dc, dr in directions:
            new_col, new_row = col + dc, row + dr
            found_piece = False

            while 0 <= new_col <= 8 and 0 <= new_row <= 9:
                target = self.get_piece(new_col, new_row)

                if not found_piece:
                    if target is None:
                        moves.append((new_col, new_row))
                    else:
                        found_piece = True
                else:
                    # 已经隔了一个棋子
                    if target is not None:
                        if not is_same_side(piece, target):
                            moves.append((new_col, new_row))
                        break
                new_col += dc
                new_row += dr

        return moves

    def _get_pawn_moves(self, col, row, piece):
        """兵/卒的走法"""
        moves = []
        is_red = is_red_piece(piece)

        if is_red:
            # 红兵过河前只能前进,过河后可左右移动
            forward = -1  # 红方向上走
            if row <= 4:
                # 未过河,只能前进
                new_row = row + forward
                if 0 <= new_row <= 9:
                    target = self.get_piece(col, new_row)
                    if target is None or not is_same_side(piece, target):
                        moves.append((col, new_row))
            else:
                # 过河
                for dc, dr in [(0, forward), (1, 0), (-1, 0)]:
                    new_col, new_row = col + dc, row + dr
                    if 0 <= new_col <= 8 and 0 <= new_row <= 9:
                        target = self.get_piece(new_col, new_row)
                        if target is None or not is_same_side(piece, target):
                            moves.append((new_col, new_row))
        else:
            # 黑卒过河前只能前进,过河后可左右移动
            forward = 1  # 黑方向上走
            if row >= 5:
                # 未过河,只能前进
                new_row = row + forward
                if 0 <= new_row <= 9:
                    target = self.get_piece(col, new_row)
                    if target is None or not is_same_side(piece, target):
                        moves.append((col, new_row))
            else:
                # 过河
                for dc, dr in [(0, forward), (1, 0), (-1, 0)]:
                    new_col, new_row = col + dc, row + dr
                    if 0 <= new_col <= 8 and 0 <= new_row <= 9:
                        target = self.get_piece(new_col, new_row)
                        if target is None or not is_same_side(piece, target):
                            moves.append((new_col, new_row))

        return moves

    def update_from_detection(self, detected_pieces):
        """
        根据视觉检测结果更新棋盘

        Args:
            detected_pieces: 棋子列表,每项包含:
                           - position: (col, row) 棋盘坐标
                             注意: row 0 = 红方底线, row 9 = 黑方底线
                           - color: 'red' 或 'black'
                           - piece_id: 棋子ID字符串 (如 'RED_R', 'BLACK_P')
        """
        # 清空棋盘(只保留线条框架)
        self.board = [[None] * 9 for _ in range(10)]

        for piece in detected_pieces:
            col, row = piece['position']
            piece_id_str = piece.get('piece_id')

            if piece_id_str and piece_id_str in PIECE_ID:
                piece_id = PIECE_ID[piece_id_str]
            elif piece['color'] == 'red':
                piece_id = PIECE_ID['RED_P']  # 默认红兵
            else:
                piece_id = PIECE_ID['BLACK_P']  # 默认黑卒

            # 检测坐标: row 0 = 红方底线, row 9 = 黑方底线 (与camera_fen_project一致)
            # 标准FEN: row 0 = 黑方底线, row 9 = 红方底线
            # 需要翻转row以匹配标准FEN
            internal_row = 9 - row

            self.set_piece(col, internal_row, piece_id)


def test():
    """测试棋盘"""
    board = XiangqiBoard()

    print("初始棋盘:")
    for row in range(10):
        row_str = f"{row}: "
        for col in range(9):
            piece = board.get_piece(col, row)
            if piece is None:
                row_str += " . "
            else:
                row_str += f"{PIECE_NAMES[piece]} "
        print(row_str)

    print("\n红车(9,0)的合法走法:")
    moves = board.get_legal_moves(0, 9)
    print(moves)

    print("\n红炮(1,7)的合法走法:")
    moves = board.get_legal_moves(1, 7)
    print(moves)

    print("\n红兵(0,6)的合法走法:")
    moves = board.get_legal_moves(0, 6)
    print(moves)


if __name__ == '__main__':
    test()
