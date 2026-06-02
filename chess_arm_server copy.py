#!/usr/bin/env python3
"""
机械臂控制服务器
运行在树莓派上，监听TCP连接接收指令并执行机械臂动作
"""

import sys
import time
import socket

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
        self.grasp_height = 11
        self.safe_height = 16.0

        if Arm_Device:
            self.arm = Arm_Device()
            print("机械臂已连接")

        if create_air_pump:
            self.pump = create_air_pump()
            print("气泵已初始化")

        self.initial_pos = [179, 179, 0, 0, 90, 65]

    def solve_ik(self, robot_pos):
        """使用IK求解器"""
        if ik is None:
            return None
        x, y, z = robot_pos
        valid, deg1, deg2, deg3, deg4 = ik.backward_kinematics(x, y, z)
        if valid:
            return [deg1, deg2, deg3, deg4, 90]
        return None

    def move_to_position(self, position, servo6_angle=57, retries=3):
        """移动到指定位置"""
        angles = self.solve_ik(position)
        if angles is None:
            print(f"IK无解: {position}")
            return False

        if self.arm:
            for attempt in range(retries):
                try:
                    self.arm.Arm_serial_servo_write6(
                        angles[0], angles[1], angles[2],
                        angles[3], angles[4], servo6_angle, 2000
                    )
                    print(f"移动到 {position}: {[f'{a:.1f}' for a in angles]}")
                    return True
                except Exception as e:
                    print(f"I2C错误 ({attempt+1}/{retries}): {e}")
                    time.sleep(0.5)
        return False

    def pump_on(self):
        if self.pump:
            self.pump.activate()
            print("气泵开启")

    def pump_off(self):
        if self.pump:
            self.pump.deactivate()
            print("气泵关闭")

    def set_initial_position(self):
        if self.arm:
            self.arm.Arm_serial_servo_write6(
                self.initial_pos[0], self.initial_pos[1], self.initial_pos[2],
                self.initial_pos[3], self.initial_pos[4], self.initial_pos[5], 2500
            )
            print("移动到初始位置")

    def execute_move(self, from_robot, to_robot, is_capture=False):
        """执行走棋序列

        Args:
            from_robot: 起始位置机器人坐标 [x, y, z]
            to_robot: 目标位置机器人坐标 [x, y, z]
            is_capture: 是否为吃子
        """
        if is_capture:
            if not self.remove_captured_piece(to_robot):
                print("警告: 移除被吃棋子失败,继续执行走棋")

        print("\n===== 开始走棋序列 =====")

        above_from = [from_robot[0], from_robot[1], self.safe_height]
        print(f"1. 移动到起始位置上方 {above_from}")
        if not self.move_to_position(above_from, servo6_angle=57):
            print("警告: 起始位置上方不可达")
        time.sleep(2.5)

        print(f"2. 下降到起始位置上方11cm")
        mid_from = [from_robot[0], from_robot[1], self.grasp_height]
        if not self.move_to_position(mid_from, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"3. 下降到起始位置 {from_robot}")
        if not self.move_to_position(from_robot, servo6_angle=57):
            print("错误: 无法移动到起始位置")
            return False
        time.sleep(2.5)

        print("4. 开启气泵吸取棋子")
        self.pump_on()
        time.sleep(1.5)

        print(f"5. 抬起到安全高度")
        safe_from = [from_robot[0], from_robot[1], 16]
        if not self.move_to_position(safe_from, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        print(f"6. 移动到目标位置上方")
        above_to = [to_robot[0], to_robot[1], 16]
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 目标位置上方不可达")
        time.sleep(2.5)

        print(f"7. 下降到目标位置上方11cm")
        mid_to = [to_robot[0], to_robot[1], 13]
        if not self.move_to_position(mid_to, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"8. 下降到目标位置 {to_robot}")
        if not self.move_to_position(to_robot, servo6_angle=57):
            print("错误: 无法移动到目标位置")
            return False
        time.sleep(2.5)

        print("9. 关闭气泵放下棋子")
        self.pump_off()
        time.sleep(1.5)

        print(f"10. 抬起到安全高度")
        safe_to = [to_robot[0], to_robot[1], self.safe_height]
        if not self.move_to_position(safe_to, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        print("===== 走棋完成 =====")

        self.set_initial_position()
        time.sleep(2.5)

        return True

    def remove_captured_piece(self, to_robot):
        """移除被吃的棋子(放到一旁)"""
        print("检测到吃子,先移除目标位置棋子")

        remove_pos = [17, 5, 9]
        intermediate_pos = [17, 8, 16]
        print(f"1. 移动到目标位置 {to_robot}")

        above_to = [to_robot[0], to_robot[1], self.safe_height]
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 目标位置上方不可达")
        time.sleep(2.5)

        print(f"2. 下降到目标位置上方11cm")
        mid_to = [to_robot[0], to_robot[1], 11]
        if not self.move_to_position(mid_to, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"3. 下降到目标位置 {to_robot}")
        if not self.move_to_position(to_robot, servo6_angle=57):
            print("错误: 无法移动到目标位置")
            return False
        time.sleep(2.5)

        print("4. 开启气泵吸取棋子")
        self.pump_on()
        time.sleep(1.5)

        print("5. 抬起到安全高度")
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        print(f"6. 移动到中间位置 {intermediate_pos}")
        if not self.move_to_position(intermediate_pos, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.5)

        print(f"7. 下降到移除位置上方11cm")
        mid_remove = [remove_pos[0], remove_pos[1], 11]
        if not self.move_to_position(mid_remove, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"8. 下降到移除位置 {remove_pos}")
        if not self.move_to_position(remove_pos, servo6_angle=57):
            print("警告: 移除位置不可达")
        time.sleep(2.5)

        print("9. 关闭气泵放下棋子")
        self.pump_off()
        time.sleep(1.5)

        print("10. 抬起到安全高度")
        if not self.move_to_position(intermediate_pos, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        return True

    def handle_command(self, cmd):
        """处理命令"""
        try:
            parts = cmd.strip().split(',')
            action = parts[0]

            if action == 'MOVE':
                # 格式: MOVE,x_from,y_from,z_from,x_to,y_to,z_to,is_capture
                from_robot = [float(parts[1]), float(parts[2]), float(parts[3])]
                to_robot = [float(parts[4]), float(parts[5]), float(parts[6])]
                is_capture = parts[7].lower() == 'true'

                self.execute_move(from_robot, to_robot, is_capture=is_capture)
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
    main()#!/usr/bin/env python3
"""
机械臂控制服务器
运行在树莓派上，监听TCP连接接收指令并执行机械臂动作
"""

import sys
import time
import socket

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
        self.grasp_height = 11
        self.safe_height = 16.0

        if Arm_Device:
            self.arm = Arm_Device()
            print("机械臂已连接")

        if create_air_pump:
            self.pump = create_air_pump()
            print("气泵已初始化")

        self.initial_pos = [179, 179, 0, 0, 90, 65]

    def solve_ik(self, robot_pos):
        """使用IK求解器"""
        if ik is None:
            return None
        x, y, z = robot_pos
        valid, deg1, deg2, deg3, deg4 = ik.backward_kinematics(x, y, z)
        if valid:
            return [deg1, deg2, deg3, deg4, 90]
        return None

    def move_to_position(self, position, servo6_angle=57, retries=3):
        """移动到指定位置"""
        angles = self.solve_ik(position)
        if angles is None:
            print(f"IK无解: {position}")
            return False

        if self.arm:
            for attempt in range(retries):
                try:
                    self.arm.Arm_serial_servo_write6(
                        angles[0], angles[1], angles[2],
                        angles[3], angles[4], servo6_angle, 2000
                    )
                    print(f"移动到 {position}: {[f'{a:.1f}' for a in angles]}")
                    return True
                except Exception as e:
                    print(f"I2C错误 ({attempt+1}/{retries}): {e}")
                    time.sleep(0.5)
        return False

    def pump_on(self):
        if self.pump:
            self.pump.activate()
            print("气泵开启")

    def pump_off(self):
        if self.pump:
            self.pump.deactivate()
            print("气泵关闭")

    def set_initial_position(self):
        if self.arm:
            self.arm.Arm_serial_servo_write6(
                self.initial_pos[0], self.initial_pos[1], self.initial_pos[2],
                self.initial_pos[3], self.initial_pos[4], self.initial_pos[5], 2500
            )
            print("移动到初始位置")

    def execute_move(self, from_robot, to_robot, is_capture=False):
        """执行走棋序列

        Args:
            from_robot: 起始位置机器人坐标 [x, y, z]
            to_robot: 目标位置机器人坐标 [x, y, z]
            is_capture: 是否为吃子
        """
        if is_capture:
            if not self.remove_captured_piece(to_robot):
                print("警告: 移除被吃棋子失败,继续执行走棋")

        print("\n===== 开始走棋序列 =====")

        above_from = [from_robot[0], from_robot[1], self.safe_height]
        print(f"1. 移动到起始位置上方 {above_from}")
        if not self.move_to_position(above_from, servo6_angle=57):
            print("警告: 起始位置上方不可达")
        time.sleep(2.5)

        print(f"2. 下降到起始位置上方11cm")
        mid_from = [from_robot[0], from_robot[1], self.grasp_height]
        if not self.move_to_position(mid_from, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"3. 下降到起始位置 {from_robot}")
        if not self.move_to_position(from_robot, servo6_angle=57):
            print("错误: 无法移动到起始位置")
            return False
        time.sleep(2.5)

        print("4. 开启气泵吸取棋子")
        self.pump_on()
        time.sleep(1.5)

        print(f"5. 抬起到安全高度")
        safe_from = [from_robot[0], from_robot[1], 16]
        if not self.move_to_position(safe_from, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        print(f"6. 移动到目标位置上方")
        above_to = [to_robot[0], to_robot[1], 16]
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 目标位置上方不可达")
        time.sleep(2.5)

        print(f"7. 下降到目标位置上方11cm")
        mid_to = [to_robot[0], to_robot[1], 13]
        if not self.move_to_position(mid_to, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"8. 下降到目标位置 {to_robot}")
        if not self.move_to_position(to_robot, servo6_angle=57):
            print("错误: 无法移动到目标位置")
            return False
        time.sleep(2.5)

        print("9. 关闭气泵放下棋子")
        self.pump_off()
        time.sleep(1.5)

        print(f"10. 抬起到安全高度")
        safe_to = [to_robot[0], to_robot[1], self.safe_height]
        if not self.move_to_position(safe_to, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        print("===== 走棋完成 =====")

        self.set_initial_position()
        time.sleep(2.5)

        return True

    def remove_captured_piece(self, to_robot):
        """移除被吃的棋子(放到一旁)"""
        print("检测到吃子,先移除目标位置棋子")

        remove_pos = [17, 5, 9]
        intermediate_pos = [17, 8, 16]
        print(f"1. 移动到目标位置 {to_robot}")

        above_to = [to_robot[0], to_robot[1], self.safe_height]
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 目标位置上方不可达")
        time.sleep(2.5)

        print(f"2. 下降到目标位置上方11cm")
        mid_to = [to_robot[0], to_robot[1], 11]
        if not self.move_to_position(mid_to, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"3. 下降到目标位置 {to_robot}")
        if not self.move_to_position(to_robot, servo6_angle=57):
            print("错误: 无法移动到目标位置")
            return False
        time.sleep(2.5)

        print("4. 开启气泵吸取棋子")
        self.pump_on()
        time.sleep(1.5)

        print("5. 抬起到安全高度")
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        print(f"6. 移动到中间位置 {intermediate_pos}")
        if not self.move_to_position(intermediate_pos, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.5)

        print(f"7. 下降到移除位置上方11cm")
        mid_remove = [remove_pos[0], remove_pos[1], 11]
        if not self.move_to_position(mid_remove, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"8. 下降到移除位置 {remove_pos}")
        if not self.move_to_position(remove_pos, servo6_angle=57):
            print("警告: 移除位置不可达")
        time.sleep(2.5)

        print("9. 关闭气泵放下棋子")
        self.pump_off()
        time.sleep(1.5)

        print("10. 抬起到安全高度")
        if not self.move_to_position(intermediate_pos, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.5)

        return True

    def handle_command(self, cmd):
        """处理命令"""
        try:
            parts = cmd.strip().split(',')
            action = parts[0]

            if action == 'MOVE':
                # 格式: MOVE,x_from,y_from,z_from,x_to,y_to,z_to,is_capture
                from_robot = [float(parts[1]), float(parts[2]), float(parts[3])]
                to_robot = [float(parts[4]), float(parts[5]), float(parts[6])]
                is_capture = parts[7].lower() == 'true'

                self.execute_move(from_robot, to_robot, is_capture=is_capture)
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
    parser.add_argument('--host', default='192.168.137.1', help='监听地址 (默认0.0.0.0)')
    parser.add_argument('--port', '-p', type=int, default=5000, help='监听端口 (默认5000)')
    args = parser.parse_args()

    server = ChessArmServer(host=args.host, port=args.port)
    server.run()


if __name__ == '__main__':
    main()


