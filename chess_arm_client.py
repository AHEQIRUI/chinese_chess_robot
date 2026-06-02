#!/usr/bin/env python3
"""
机械臂控制客户端
运行在电脑上，获取云端走法并发送指令给树莓派服务器
"""

import sys
import socket

sys.path.insert(0, '.')

try:
    from cloud_query import get_best_move
except ImportError:
    print("错误: 无法导入cloud_query")
    get_best_move = None


class ChessArmClient:
    """机械臂控制客户端"""

    def __init__(self, server_host, server_port=5000, arm_color='red'):
        self.server_host = server_host
        self.server_port = server_port
        self.arm_color = arm_color
        self.socket = None

    def connect(self):
        """连接到服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            print(f"已连接到服务器 {self.server_host}:{self.server_port}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def send_command(self, cmd):
        """发送命令并接收响应"""
        try:
            self.socket.sendall((cmd + '\n').encode('utf-8'))
            response = self.socket.recv(1024).decode('utf-8')
            return response
        except Exception as e:
            print(f"发送命令失败: {e}")
            return None

    def close(self):
        """关闭连接"""
        if self.socket:
            self.socket.close()
            self.socket = None

    def is_capture_from_fen(self, fen, to_pos):
        """从已知FEN判断目标位置是否有棋子(吃子判定)

        参考 chess_arm_control.detect_capture:
        检查目标棋盘坐标上是否存在棋子
        """
        col, row = to_pos
        # 去掉可能的后缀 (如 " w" / " b")
        board_fen = fen.split()[0]
        rows = board_fen.split('/')
        # ucci_to_numeric 已做了 9-d 转换, row 就是 FEN 索引
        fen_row = row
        if fen_row < 0 or fen_row >= len(rows):
            return False, None

        # 将FEN行展开为完整9字符 ('.' = 空)
        expanded = ''
        for ch in rows[fen_row]:
            if ch.isdigit():
                expanded += '.' * int(ch)
            else:
                expanded += ch

        if col < len(expanded) and expanded[col] != '.':
            # 提取棋子信息, 与 detect_capture 返回格式一致
            fen_char = expanded[col]
            piece_type = {'R': '车', 'N': '马', 'B': '象', 'A': '仕', 'K': '帅',
                          'C': '炮', 'P': '兵',
                          'r': '車', 'n': '馬', 'b': '相', 'a': '士', 'k': '将',
                          'c': '砲', 'p': '卒'}.get(fen_char, '?')
            color = 'red' if fen_char.isupper() else 'black'
            return True, {'type': piece_type, 'color': color, 'fen_char': fen_char}
        return False, None

    def send_move(self, from_robot, to_robot, is_capture=False):
        """发送走棋命令"""
        cmd = f"MOVE,{from_robot[0]},{from_robot[1]},{from_robot[2]},{to_robot[0]},{to_robot[1]},{to_robot[2]},{str(is_capture).lower()}"
        print(f"发送命令: {cmd}")
        response = self.send_command(cmd)
        print(f"服务器响应: {response}")
        return response == "OK"

    def wait_for_user_confirm(self):
        """等待用户确认"""
        print("\n" + "=" * 50)
        print("按 'g' 执行走棋, 'q' 取消, 'r' 刷新重新检测棋盘")
        print("=" * 50)
        while True:
            key = input("输入: ").strip().lower()
            if key == 'g':
                return True
            elif key == 'q':
                return False
            elif key == 'r':
                return 'refresh'

    def print_board(self, fen):
        """在终端打印当前棋盘局面，参考 xiangqi.py 的 print_pos 风格"""
        FEN_TO_CN = {'R': '车', 'N': '马', 'B': '象', 'A': '仕', 'K': '帅',
                      'C': '炮', 'P': '兵',
                      'r': '車', 'n': '馬', 'b': '相', 'a': '士', 'k': '将',
                      'c': '砲', 'p': '卒', '.': '·'}

        RED = '\033[91m'
        RESET = '\033[0m'

        print("\n  当前局面")
        rows = fen.split('/')
        for i, row_str in enumerate(rows):
            # 红方棋子用红色
            display = []
            for ch in row_str:
                if ch.isdigit():
                    display.append('.  ' * int(ch))
                elif ch.isupper():
                    display.append(f"{RED}{FEN_TO_CN.get(ch, ch)}{RESET} ")
                else:
                    display.append(FEN_TO_CN.get(ch, ch) + ' ')
            row_label = 9 - i
            print(f" {row_label}  {''.join(display).strip()}")

        print('    a  b  c  d  e  f  g  h  i\n')

    def get_move_from_cloud(self):
        """从云端获取最佳走法"""
        if get_best_move is None:
            print("错误: cloud_query模块不可用")
            return None

        print(f"\n检测棋盘并查询最佳走法 (机械臂颜色: {self.arm_color})")
        result = get_best_move(arm_color=self.arm_color, verbose=True)

        if not result or not result.get('success'):
            print(f"获取走法失败: {result.get('error') if result else '未知错误'}")
            return None

        from_robot = result.get('from_robot')
        to_robot = result.get('to_robot')

        if not from_robot or not to_robot:
            print("错误: 机器人坐标无效")
            return None

        # 打印当前局面
        if result.get('fen'):
            self.print_board(result['fen'])

        print(f"\n最佳走法: {result['best_move']}")
        print(f"起始位置(机器人): {from_robot}")
        print(f"目标位置(机器人): {to_robot}")

        result['_from_robot'] = from_robot
        result['_to_robot'] = to_robot
        return result

    def run(self):
        """运行客户端"""
        if not self.connect():
            return False

        try:
            result = None
            while True:
                if result is None:
                    print("\n按 'r' 检测棋盘获取走法, 'q' 退出")
                    action = self.wait_for_user_confirm()
                    if action is False:
                        print("已退出")
                        return False
                    elif action == 'refresh':
                        result = self.get_move_from_cloud()
                        continue
                    else:
                        print("请先按 'r' 检测棋盘")
                        continue
                else:
                    print(f"\n当前走法: {result['best_move']} ({result['from_display']}->{result['to_display']})")
                    action = self.wait_for_user_confirm()
                    if action is False:
                        print("已取消走棋，等待新指令...")
                        result = None
                        continue
                    elif action == 'refresh':
                        result = self.get_move_from_cloud()
                        continue

                    # 执行走棋
                    from_robot = result['_from_robot']
                    to_robot = result['_to_robot']

                    is_capture, captured = self.is_capture_from_fen(result['fen'], result.get('to_pos_orig') or result['to_pos'])
                    if is_capture:
                        print(f"检测到吃子: {captured['type']} at {result['to_display']}")

                    self.send_move(from_robot, to_robot, is_capture)
                    print("\n走棋完成，等待新指令...")
                    result = None

        finally:
            self.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='机械臂控制客户端')
    parser.add_argument('--host', default='192.168.137.60', help='树莓派IP地址')
    parser.add_argument('--port', '-p', type=int, default=5000, help='服务器端口 (默认5000)')
    parser.add_argument('--color', '-c', type=str, default='black',
                       choices=['red', 'black'],
                       help='机械臂控制方的颜色 (默认red)')
    args = parser.parse_args()

    client = ChessArmClient(server_host=args.host, server_port=args.port, arm_color=args.color)
    client.run()


if __name__ == '__main__':
    main()