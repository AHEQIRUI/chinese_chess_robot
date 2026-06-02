#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
中国象棋云端API调用模块
使用 chessdb.cn 的 querybest 接口
"""

import urllib.request
import urllib.parse

from xiangqi import board_to_fen, Position, initial, parse, render, A1, BOARD_COLUMN


BASE_URL = "http://www.chessdb.cn/chessdb.php"
OPENING_FEN = "rnbakabnr/9/1c5c1/p3p1p1p/9/2p6/P3P1P1P/1CN4C1/9/R1BAKABNR w"


class XiangqiCloudAPI:
    """中国象棋云端API调用器"""

    def __init__(self, timeout=10):
        self.timeout = timeout

    def query_best(self, board):
        """
        查询最佳走法

        Args:
            board: FEN格式字符串(完整格式,包含 w/b)

        Returns:
            str: UCCI格式走法 (如 "c3c4") 或 None
        """
        try:
            params = {"action": "querybest", "board": board}
            query = urllib.parse.urlencode(params)
            # chessdb需要未编码的斜杠
            query = query.replace('%2F', '/')
            url = f"{BASE_URL}?{query}"

            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                result = resp.read().decode("utf-8")

            if result.startswith("move:"):
                move = result.split(":")[1].rstrip('\x00\n\r').strip()
                return move if len(move) == 4 else None
            return result

        except Exception as e:
            print(f"查询失败: {e}")
            return None

    def query(self, position=None, fen=None):
        """
        查询FEN局面,获取AI走法建议

        Args:
            position: xiangqi.Position 对象 (优先使用)
            fen: FEN格式字符串(完整格式,包含局面和轮次)

        Returns:
            dict: {'success': True, 'best_move': 'c3c4', 'best_move_ucci': ((2,2), (2,3)),
                   'position': Position, 'from_idx': int, 'to_idx': int}
                  或 {'success': False, 'error': '...'}
        """
        # 如果提供了 position 对象,使用 xiangqi.py 的 FEN 生成
        if position is not None and hasattr(position, 'board'):
            fen_position = board_to_fen(position.board, True)
        else:
            fen_position = fen

        print(f"查询FEN: {fen_position}")

        best_move = self.query_best(fen_position)
        if best_move and best_move not in ('invalid board', 'nobestmove') and len(best_move) == 4:
            from_idx = parse(best_move[:2])
            to_idx = parse(best_move[2:])
            return {
                'success': True,
                'best_move': best_move,
                'best_move_ucci': self._ucci_to_coordinates(best_move),
                'position': position,
                'from_idx': from_idx,
                'to_idx': to_idx
            }
        else:
            return {'success': False, 'error': best_move}

    def _ucci_to_coordinates(self, ucci_move):
        """
        将UCCI格式走法转换为棋盘坐标

        UCCI格式: d9y0 表示从(d列,9行)到(y列,0行)
        列映射: a-i -> 0-8, 行映射: 0-9

        Returns:
            tuple: ((from_col, from_row), (to_col, to_row)) 或 None
        """
        if not ucci_move or len(ucci_move) != 4:
            return None

        try:
            from_col = ord(ucci_move[0].lower()) - ord('a')
            to_col = ord(ucci_move[2].lower()) - ord('a')
            from_row = int(ucci_move[1])
            to_row = int(ucci_move[3])

            # UCCI行0-9对应内部坐标0-9
            return ((from_col, from_row), (to_col, to_row))
        except Exception as e:
            print(f"坐标转换错误: {e}")
            return None

    def query_simple(self, position=None, fen=None):
        """
        简化查询:返回最佳走法坐标

        Args:
            position: xiangqi.Position 对象 (优先使用)
            fen: FEN格式字符串

        Returns:
            tuple: ((from_col, from_row), (to_col, to_row)) 或 None
        """
        result = self.query(position, fen)
        if result.get('success'):
            return result.get('best_move_ucci')
        return None


def test():
    """测试API"""
    api = XiangqiCloudAPI()
    print(f"测试开局: {OPENING_FEN}")
    result = api.query(OPENING_FEN)
    if result.get('success'):
        print(f"最佳走法: {result.get('best_move')}")
        print(f"坐标: {result.get('best_move_ucci')}")
    else:
        print(f"失败: {result.get('error')}")


if __name__ == "__main__":
    test()