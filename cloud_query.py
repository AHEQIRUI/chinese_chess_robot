#!/usr/bin/env python3
"""
获取云端所有合法走法和最佳走法
使用piece_detector检测棋盘,通过chessdb.cn云端API查询
"""

import sys

from piece_detector import PieceDetector
from board_detector import BoardDetector
from board_to_robot import BoardToRobotMapper
from coord_utils import numeric_to_ucci, ucci_to_numeric
from simple_engine import analyze
import urllib.request
import urllib.parse


BASE_URL = "http://www.chessdb.cn/chessdb.php"


def query_all_moves(fen):
    """
    查询FEN局面的所有合法走法

    Args:
        fen: FEN格式字符串(完整格式,包含 w/b)

    Returns:
        list: UCCI格式走法列表 或 None
    """
    try:
        params = {"action": "queryall", "board": fen}
        query = urllib.parse.urlencode(params)
        query = query.replace('%2F', '/')
        url = f"{BASE_URL}?{query}"

        with urllib.request.urlopen(url, timeout=10) as resp:
            result = resp.read().decode("utf-8")

        if result.startswith("move:"):
            moves = []
            for item in result.split('|'):
                if item.startswith("move:"):
                    move = item.split(",")[0].split(":")[1].strip()
                    if len(move) == 4:
                        moves.append(move)
            return moves if moves else None
        return None
    except Exception as e:
        print(f"查询所有走法失败: {e}")
        return None


def rotate_move_180(move):
    """
    将走法旋转180度(黑方视角转换)

    Args:
        move: UCCI格式走法 如 'c3c4'

    Returns:
        str: 旋转后的走法 如 'g6g7'
    """
    if len(move) != 4:
        return move
    # 180度旋转: col -> 8-col, row -> 9-row
    from_u = move[:2]
    to_u = move[2:]
    from_col = ord(from_u[0].lower()) - ord('a')
    from_row = int(from_u[1])
    to_col = ord(to_u[0].lower()) - ord('a')
    to_row = int(to_u[1])
    new_from = f"{chr(ord('a') + 8 - from_col)}{9 - from_row}"
    new_to = f"{chr(ord('a') + 8 - to_col)}{9 - to_row}"
    return new_from + new_to


def query_best_with_details(fen):
    """
    使用querypv获取最佳走法及详细分析

    Args:
        fen: FEN格式字符串(完整格式,包含 w/b)

    Returns:
        dict: {
            'best_move': 'c3c4',
            'score': -50,
            'depth': 12,
            'pv': ['c3c4', 'e7e6', 'h3h4'],
            'pv_str': 'c3c4 e7e6 h3h4'
        }
    """
    try:
        params = {"action": "querypv", "board": fen}
        query = urllib.parse.urlencode(params)
        query = query.replace('%2F', '/')
        url = f"{BASE_URL}?{query}"

        with urllib.request.urlopen(url, timeout=15) as resp:
            result = resp.read().decode("utf-8")

        if "score:" in result or "pv:" in result:
            parts = result.rstrip('\x00\n\r').split(",")

            # 解析最佳走法
            best_move = None
            for part in parts:
                if part.startswith("pv:"):
                    moves_in_pv = part.split(":")[1].strip().split("|")
                    if moves_in_pv:
                        best_move = moves_in_pv[0]
                        break

            # 解析分数
            score = 0
            for part in parts:
                if part.startswith("score:"):
                    try:
                        score = int(part.split(":")[1])
                    except:
                        pass

            # 解析深度
            depth = 0
            for part in parts:
                if part.startswith("depth:"):
                    try:
                        depth = int(part.split(":")[1])
                    except:
                        pass

            # 解析PV线 (格式: pv:h0g2|c6c5|b0c2|...)
            pv = []
            pv_str = ""
            for part in parts:
                if part.startswith("pv:"):
                    pv_str = part.split(":", 1)[1].strip()
                    pv = pv_str.split("|")
                    break

            return {
                'best_move': best_move if best_move and len(best_move) == 4 else None,
                'score': score,
                'depth': depth,
                'pv': pv,
                'pv_str': " ".join(pv)
            }
        return None
    except Exception as e:
        print(f"查询详细着法失败: {e}")
        return None


def get_best_move(arm_color='red', verbose=True):
    """
    检测当前棋盘,获取云端所有合法走法和最佳走法

    Args:
        arm_color: 机械臂控制方的颜色 ('red' 或 'black')
        verbose: 是否打印详细信息

    Returns:
        dict: {
            'success': True/False,
            'all_moves': ['a1a2', 'b1c3', ...],
            'best_move': 'a1a2',
            'score': -50,
            'depth': 12,
            'pv': ['a1a2', 'b2b3', ...],
            'pv_str': 'a1a2 b2b3 ...',
            'from_pos': (col, row),
            'to_pos': (col, row),
            'from_display': 'a9',
            'to_display': 'a0',
            'from_robot': [x, y, z],
            'to_robot': [x, y, z],
            'fen': '...',
            'arm_color': 'red'/'black'
        }
    """
    # 初始化检测器
    board_detector = BoardDetector()
    piece_detector = PieceDetector(board_detector=board_detector)
    mapper = BoardToRobotMapper()

    # 打开相机
    import cv2
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    try:
        ret, frame = cap.read()
        if not ret:
            return {'success': False, 'error': '无法读取相机画面'}

        # 检测棋子
        pieces = piece_detector.detect_pieces(frame)
        if not pieces:
            return {'success': False, 'error': '未检测到棋子'}

        # 转换为FEN (piece_detector已处理颜色映射)
        fen = piece_detector.pieces_to_fen_standard(pieces)

        # 追加颜色标识
        side_suffix = 'w' if arm_color == 'red' else 'b'
        fen_full = f"{fen} {side_suffix}"

        if verbose:
            print(f"FEN: {fen_full}")
            print(f"机械臂颜色: {arm_color}")

        # 查询所有走法
        all_moves = query_all_moves(fen_full)

        # 使用本地引擎查询最佳走法
        best_move = analyze(fen_full, depth=25)
        score = 0
        depth = 25
        pv = [best_move] if best_move else []
        pv_str = best_move if best_move else ""

        # 如果无PV走法,返回失败
        if not best_move:
            if verbose:
                print(f"无最佳走法")
            return {
                'success': False,
                'all_moves': all_moves or [],
                'error': 'no best move'
            }

        # 如果机械臂是黑方,将着法旋转180度(转换视角)
        # 保存原始坐标用于吃子判定
        best_move_orig = best_move
        if arm_color == 'black':
            best_move = rotate_move_180(best_move)
            score = -score  # 分数也需要反转
            if all_moves:
                all_moves = [rotate_move_180(m) for m in all_moves]
            if pv:
                pv = [rotate_move_180(m) for m in pv]
                pv_str = " ".join(pv)

        if verbose:
            if all_moves:
                print(f"所有合法走法 ({len(all_moves)}种):")
                for move in all_moves[:20]:
                    print(f"  {move}")
                if len(all_moves) > 20:
                    print(f"  ... 还有{len(all_moves)-20}种")
            else:
                print("未查询到所有走法")

        if best_move and len(best_move) == 4:
            # best_move 是 UCCI 格式 (a0i9), 需要转换为内部坐标
            from_internal = ucci_to_numeric(best_move[:2])
            to_internal = ucci_to_numeric(best_move[2:])
            if from_internal and to_internal:
                from_col, from_row = from_internal
                to_col, to_row = to_internal
                from_robot = [round(x, 1) for x in mapper.board_to_robot(from_col, from_row, 8.5).tolist()]
                to_robot = [round(x, 1) for x in mapper.board_to_robot(to_col, to_row, 8.5).tolist()]
                from_display = numeric_to_ucci(from_col, from_row)
                to_display = numeric_to_ucci(to_col, to_row)
            else:
                from_robot = None
                to_robot = None
                from_display = None
                to_display = None
                from_col, from_row = None, None
                to_col, to_row = None, None
                return {
                    'success': False,
                    'all_moves': all_moves or [],
                    'error': '坐标转换失败'
                }
            if verbose:
                print(f"最佳走法: {best_move}")
                print(f"分数: {score}, 深度: {depth}")
                if pv:
                    print(f"PV线: {pv_str}")
                print(f"内部坐标: (({from_col}, {from_row}), ({to_col}, {to_row}))")
                print(f"显示坐标: {from_display} -> {to_display}")
                print(f"机器人起始: {from_robot}")
                print(f"机器人目标: {to_robot}")
            return {
                'success': True,
                'all_moves': all_moves or [],
                'best_move': best_move,
                'score': score,
                'depth': depth,
                'pv': pv,
                'pv_str': pv_str,
                'from_pos': from_internal,
                'to_pos': to_internal,
                'from_pos_orig': ucci_to_numeric(best_move_orig[:2]),
                'to_pos_orig': ucci_to_numeric(best_move_orig[2:]),
                'from_display': from_display,
                'to_display': to_display,
                'from_robot': from_robot,
                'to_robot': to_robot,
                'fen': fen,
                'arm_color': arm_color
            }

    finally:
        cap.release()


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='获取云端所有合法走法和最佳走法')
    parser.add_argument('--color', '-c', type=str, default='black',
                       choices=['red', 'black'],
                       help='机械臂控制方的颜色 (默认red)')
    args = parser.parse_args()

    result = get_best_move(arm_color=args.color)
    if result and result.get('success'):
        print(f"\n结果:")
        print(f"  最佳走法: {result['best_move']}")
        print(f"  分数: {result['score']}, 深度: {result['depth']}")
        if result['pv_str']:
            print(f"  PV线: {result['pv_str']}")
        print(f"  显示坐标: {result['from_display']} -> {result['to_display']}")
        print(f"  内部坐标: {result['from_pos']} -> {result['to_pos']}")
        print(f"  起始位置(机器人): {result['from_robot']}")
        print(f"  目标位置(机器人): {result['to_robot']}")
        print(f"  所有走法数: {len(result['all_moves'])}")
    else:
        print(f"\n失败: {result.get('error') if result else '未知错误'}")
        sys.exit(1)


if __name__ == '__main__':
    main()