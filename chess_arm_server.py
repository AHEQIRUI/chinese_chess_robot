#!/usr/bin/env python3
"""
机械臂控制服务器
运行在树莓派上，监听TCP连接接收指令并执行机械臂动作
"""

import sys
import time
import socket
import math

sys.path.insert(0, 'src')
sys.path.insert(0, 'xq_src')

try:
    from Arm_Lib import Arm_Device
except ImportError:
    print("警告: 无法导入Arm_Lib")
    Arm_Device = None

try:
    import ik
except ImportError:
    print("错误: 无法导入ik")
    ik = None

try:
    from air_pump import create_air_pump
except ImportError:
    print("警告: 无法导入air_pump")
    create_air_pump = None


class ChessArmServer:
    """机械臂控制服务器"""

    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.arm = None
        self.pump = None

        self.grasp_height = 8.0
        self.safe_height = 15.0
        self.piece_height = 5  # 棋子高度（统一）

        self.z_correction_factor = 0.15

        self.initial_pos = [179, 179, 0, 0, 90, 65]

        if Arm_Device:
            self.arm = Arm_Device()
            print("机械臂已连接")
            self.set_initial_position()
            time.sleep(2.5)
        else:
            print("警告: 机械臂未连接, 模拟模式")

        if create_air_pump:
            self.pump = create_air_pump()
            print("气泵已初始化")

    def get_piece_height(self, move_desc=""):
        """返回棋子高度（统一高度）"""
        return self.piece_height

    def solve_ik(self, robot_pos):
        """使用IK求解器"""
        if ik is None:
            return None
        x, y, z = robot_pos
        z = self.get_corrected_z(x, y, z)
        valid, deg1, deg2, deg3, deg4 = ik.backward_kinematics(x, y, z)
        if valid:
            return [deg1, deg2, deg3, deg4, 90, 0]
        return None

    def get_corrected_z(self, x, y, z):
        """计算校正后的Z坐标

        公式: z_corrected = z + k * sqrt(x^2 + y^2)
        """
        distance = math.sqrt(x**2 + y**2)
        return z + self.z_correction_factor * distance

    def move_to_position(self, position, servo6_angle=None, retries=3):
        """移动到指定位置

        Args:
            position: [x, y, z] 目标位置
            servo6_angle: 气泵角度, None=保持当前
            retries: 重试次数
        """
        angles = self.solve_ik(position)
        if angles is None:
            print(f"IK无解: {position}")
            return False

        if servo6_angle is not None:
            angles[5] = servo6_angle

        if self.arm:
            for attempt in range(retries):
                try:
                    self.arm.Arm_serial_servo_write6(
                        angles[0], angles[1], angles[2],
                        angles[3], angles[4], angles[5], 2000
                    )
                    print(f"移动到 {position}: {[f'{a:.1f}' for a in angles]}")
                    return True
                except Exception as e:
                    print(f"I2C错误 ({attempt+1}/{retries}): {e}")
                    if attempt < retries - 1:
                        print("重新执行该步骤...")
                    time.sleep(2.5)
        else:
            print(f"[模拟] 移动到 {position}")
            return True
        return False

    def pump_on(self):
        """开启气泵"""
        if self.pump:
            self.pump.activate()
            print("气泵: 开启")

    def pump_off(self):
        """关闭气泵"""
        if self.pump:
            self.pump.deactivate()
            print("气泵: 关闭")

    def set_initial_position(self):
        """移动到初始位置"""
        if self.arm:
            self.arm.Arm_serial_servo_write6(
                self.initial_pos[0], self.initial_pos[1], self.initial_pos[2],
                self.initial_pos[3], self.initial_pos[4], self.initial_pos[5], 2000
            )
            print("移动到初始位置")

    def execute_move(self, from_robot, to_robot, is_capture=False, move_desc=""):
        """执行走棋序列: 初始位置 → 起始位置上方 → 一次下降 → 二次下降 → 吸取 → 抬升 → 目标位置上方 → 一次下降 → 二次下降 → 放置 → 抬升 → 初始位置"""
        print(f"\n===== 执行走棋 =====")
        if move_desc:
            print(f"走棋描述: {move_desc}")
            if '吃' in move_desc:
                print("动作: 吃子")
            else:
                print("动作: 移动")
        else:
            print(f"从: {from_robot}")
            print(f"到: {to_robot}")
            print(f"吃子: {is_capture}")

        above_from = [from_robot[0], from_robot[1], self.safe_height]
        above_to = [to_robot[0], to_robot[1], self.safe_height]
        half_down = [from_robot[0], from_robot[1], 8.0]  # 一次下降高度固定为9

        # 获取棋子高度
        piece_height = self.get_piece_height(move_desc)

        # 1. 初始位置
        print("#1 初始位置")

        # 2. 起始位置上方
        print(f"#2 起始位置上方 {above_from}")
        self.move_to_position(above_from, servo6_angle=57)
        time.sleep(2.5)

        # 3. 一次下降
        print(f"#3 一次下降 {half_down}")
        self.move_to_position(half_down, servo6_angle=57)
        time.sleep(3)

        # 3.5. 二次下降（到位，使用棋子高度）
        from_ground = [from_robot[0], from_robot[1], piece_height]
        print(f"#3.5 二次下降 {from_ground} (棋子高度: {piece_height})")
        self.move_to_position(from_ground, servo6_angle=57)
        time.sleep(3)

        # 4. 吸取
        print("#4 吸取棋子")
        self.pump_on()
        time.sleep(2.0)

        # 5. 抬升
        print(f"#5 抬升 {above_from}")
        self.move_to_position(above_from, servo6_angle=57)
        time.sleep(2.5)

        # 6. 目标位置上方
        print(f"#6 目标位置上方 {above_to}")
        self.move_to_position(above_to, servo6_angle=57)
        time.sleep(2.5)

        # 6.5. 一次下降
        half_down_to = [to_robot[0], to_robot[1], 8.0]
        print(f"#6.5 一次下降 {half_down_to}")
        self.move_to_position(half_down_to, servo6_angle=57)
        time.sleep(2.5)

        # 6.7. 二次下降（到位）
        to_ground = [to_robot[0], to_robot[1], piece_height]
        print(f"#6.7 二次下降 {to_ground}")
        self.move_to_position(to_ground, servo6_angle=57)
        time.sleep(2.5)

        # 7. 放置
        print("#7 放置棋子")
        self.pump_off()
        time.sleep(2.0)

        # 8. 抬升到目标位置上方
        print(f"#8 抬升到目标位置上方 {above_to}")
        self.move_to_position(above_to, servo6_angle=57)
        time.sleep(2.5)

        # 9. 初始位置
        print("#9 初始位置")
        self.set_initial_position()
        time.sleep(2.5)

        print("===== 走棋完成 =====")
        return True

    def remove_captured_piece(self, to_robot, move_desc=""):
        """移除被吃棋子: 初始位置 → 目标上方 → 一次下降 → 二次下降 → 吸取 → 抬升 → 丢弃位置上方 → 下降 → 放置 → 抬升 → 初始位置"""
        print(f"\n===== 移除被吃棋子 =====")
        if move_desc:
            print(f"走棋描述: {move_desc}")
        else:
            print(f"位置: {to_robot}")

        discard_pos = [20, 6, 7]
        above_to = [to_robot[0], to_robot[1], self.safe_height]
        above_discard = [20, 6, self.safe_height]
        half_down_to = [to_robot[0], to_robot[1], 8.0]  # 一次下降高度固定为9

        # 获取棋子高度
        piece_height = self.get_piece_height(move_desc)

        # 1. 初始位置
        print("#1 初始位置")

        # 2. 目标上方
        print(f"#2 目标上方 {above_to}")
        self.move_to_position(above_to, servo6_angle=57)
        time.sleep(2.5)

        # 3. 一次下降
        print(f"#3 一次下降 {half_down_to}")
        self.move_to_position(half_down_to, servo6_angle=57)
        time.sleep(2.5)

        # 3.5. 二次下降（到位，使用棋子高度）
        to_ground = [to_robot[0], to_robot[1], piece_height]
        print(f"#3.5 二次下降 {to_ground} (棋子高度: {piece_height})")
        self.move_to_position(to_ground, servo6_angle=57)
        time.sleep(2.5)

        # 4. 吸取
        print("#4 吸取棋子")
        self.pump_on()
        time.sleep(2.0)

        # 5. 抬升
        print(f"#5 抬升 {above_to}")
        self.move_to_position(above_to, servo6_angle=57)
        time.sleep(2.5)

        # 6. 丢弃位置上方
        print(f"#6 丢弃位置上方 {above_discard}")
        self.move_to_position(above_discard, servo6_angle=57)
        time.sleep(2.5)

        # 7. 下降到放置位置
        print(f"#7 下降到放置位置 {discard_pos}")
        self.move_to_position(discard_pos, servo6_angle=57)
        time.sleep(2.5)

        # 8. 放置
        print("#8 放置棋子")
        self.pump_off()
        time.sleep(2.0)

        # 9. 抬升到丢弃位置上方
        print(f"#9 抬升到丢弃位置上方 {above_discard}")
        self.move_to_position(above_discard, servo6_angle=57)
        time.sleep(2.5)

        print("===== 移除完成 =====")
        return True

    def handle_command(self, cmd):
        """处理命令"""
        try:
            parts = cmd.strip().split(',')
            action = parts[0]

            if action == 'MOVE':
                from_robot = [float(parts[1]), float(parts[2]), float(parts[3])]
                to_robot = [float(parts[4]), float(parts[5]), float(parts[6])]
                is_capture = parts[7].lower() == 'true'
                move_desc = parts[8] if len(parts) > 8 else ''

                if move_desc:
                    print(f"走棋描述: {move_desc}")

                if is_capture:
                    self.remove_captured_piece(to_robot, move_desc)

                self.execute_move(from_robot, to_robot, is_capture, move_desc)
                return "OK"

            elif action == 'HOME':
                self.set_initial_position()
                return "OK"

            elif action == 'PUMP_ON':
                self.pump_on()
                return "OK"

            elif action == 'PUMP_OFF':
                self.pump_off()
                return "OK"

            elif action == 'QUIT':
                return "QUIT"

            else:
                return f"UNKNOWN: {action}"

        except Exception as e:
            return f"ERROR: {e}"

    def run(self):
        """启动服务器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)

        print(f"机械臂服务器已启动，监听 {self.host}:{self.port}")

        self.set_initial_position()

        while True:
            try:
                client_socket, addr = server_socket.accept()
                print(f"连接来自: {addr}")

                while True:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break

                    print(f"收到命令: {data}")
                    response = self.handle_command(data)
                    client_socket.sendall(response.encode('utf-8'))

                    if response == "QUIT":
                        client_socket.close()
                        print("客户端断开连接")
                        break

                client_socket.close()

            except KeyboardInterrupt:
                print("\n服务器关闭")
                break
            except Exception as e:
                print(f"错误: {e}")

        server_socket.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='机械臂控制服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认0.0.0.0)')
    parser.add_argument('--port', '-p', type=int, default=5000, help='监听端口 (默认5000)')
    args = parser.parse_args()

    server = ChessArmServer(host=args.host, port=args.port)
    server.run()


if __name__ == '__main__':
    main()