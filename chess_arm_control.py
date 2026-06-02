#!/usr/bin/env python3
"""
机械臂走棋控制程序
使用气泵控制棋子移动
"""

import sys
import time

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
    from board_to_robot import BoardToRobotMapper
except ImportError:
    print("错误: 无法导入board_to_robot")
    BoardToRobotMapper = None

try:
    from air_pump import AirPump
except ImportError:
    print("警告: 无法导入air_pump")
    AirPump = None

try:
    from cloud_query import get_best_move
except ImportError:
    print("错误: 无法导入cloud_query")
    get_best_move = None


class ChessArmController:
    """机械臂走棋控制器"""

    def __init__(self, arm_color='red'):
        self.arm_color = arm_color

        if Arm_Device:
            self.arm = Arm_Device()
            print("机械臂已连接")
        else:
            self.arm = None

        if BoardToRobotMapper:
            self.mapper = BoardToRobotMapper()
            print("棋盘坐标映射器已加载")
        else:
            self.mapper = None

        if AirPump:
            self.pump = AirPump()
            print("气泵已初始化")
        else:
            self.pump = None

        self.initial_pos = [179, 179, 0, 0, 90, 65]
        self.set_initial_position()
        self.grasp_height = 8.0
        self.safe_height = 18.0

    def board_to_robot_pos(self, col, row, z_height=None):
        """将棋盘坐标转换为机器人坐标"""
        if self.mapper is None:
            return None
        if z_height is None:
            z_height = self.grasp_height
        return self.mapper.board_to_robot(col, row, z_height)

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
        """开启气泵"""
        if self.pump:
            self.pump.activate()
            print("气泵开启")

    def pump_off(self):
        """关闭气泵"""
        if self.pump:
            self.pump.deactivate()
            print("气泵关闭")

    def set_initial_position(self):
        """移动到初始位置"""
        if self.arm:
            self.arm.Arm_serial_servo_write6(
                self.initial_pos[0], self.initial_pos[1], self.initial_pos[2],
                self.initial_pos[3], self.initial_pos[4], self.initial_pos[5], 2000
            )
            print(f"移动到初始位置")

    def detect_capture(self, to_pos):
        """检测目标位置是否有棋子(吃子判定)

        Args:
            to_pos: 目标位置 (col, row)

        Returns:
            tuple: (is_capture, piece_info) 或 (False, None)
        """
        try:
            import cv2
            from piece_detector import PieceDetector
            from board_detector import BoardDetector

            board_detector = BoardDetector()
            piece_detector = PieceDetector(board_detector=board_detector)

            cap = cv2.VideoCapture(0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return False, None

            pieces = piece_detector.detect_pieces(frame)

            col, row = to_pos
            for piece in pieces:
                pc, pr = piece['position']
                if pc == col and pr == row:
                    return True, piece

            return False, None
        except Exception as e:
            print(f"检测吃子失败: {e}")
            return False, None

    def remove_captured_piece(self, to_robot):
        """移除被吃的棋子(放到一旁)"""
        print("检测到吃子,先移除目标位置棋子")

        remove_pos = [17, 5, 8]
        intermediate_pos = [17, 8, 18]
        print(f"1. 移动到目标位置 {to_robot}")

        above_to = [to_robot[0], to_robot[1], self.safe_height]
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 目标位置上方不可达")
        time.sleep(2.0)

        print(f"2. 下降到目标位置 {to_robot}")
        if not self.move_to_position(to_robot, servo6_angle=57):
            print("错误: 无法移动到目标位置")
            return False
        time.sleep(2.0)

        print("3. 开启气泵吸取棋子")
        self.pump_on()
        time.sleep(1.0)

        print("4. 抬起到安全高度")
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.0)

        print(f"5. 移动到中间位置 {intermediate_pos}")
        if not self.move_to_position(intermediate_pos, servo6_angle=57):
            print("警告: 中间位置不可达")
        time.sleep(2.0)

        print(f"6. 下降到移除位置 {remove_pos}")
        if not self.move_to_position(remove_pos, servo6_angle=57):
            print("警告: 移除位置不可达")
        time.sleep(2.0)

        print("7. 关闭气泵放下棋子")
        self.pump_off()
        time.sleep(1.0)

        print("8. 抬起到安全高度")
        if not self.move_to_position(intermediate_pos, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.0)

        return True

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
        time.sleep(2.0)

        print(f"2. 下降到起始位置 {from_robot}")
        if not self.move_to_position(from_robot, servo6_angle=57):
            print("错误: 无法移动到起始位置")
            return False
        time.sleep(2.0)

        print("3. 开启气泵吸取棋子")
        self.pump_on()
        time.sleep(1.0)

        print(f"4. 抬起到安全高度")
        safe_from = [from_robot[0], from_robot[1], 12]
        safe_from2 = [from_robot[0], from_robot[1],18]
        if not self.move_to_position(safe_from, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.0)

        print(f"5. 移动到目标位置上方")
        above_to = [to_robot[0], to_robot[1], 18]
        if not self.move_to_position(above_to, servo6_angle=57):
            print("警告: 目标位置上方不可达")
        time.sleep(2.0)

        print(f"6. 下降到目标位置 {to_robot}")
        if not self.move_to_position(to_robot, servo6_angle=57):
            print("错误: 无法移动到目标位置")
            return False
        time.sleep(2.0)

        print("7. 关闭气泵放下棋子")
        self.pump_off()
        time.sleep(1.0)

        print(f"8. 抬起到安全高度")
        if not self.move_to_position(safe_from2, servo6_angle=57):
            print("警告: 抬起失败")
        time.sleep(2.0)

        print("===== 走棋完成 =====")

        self.set_initial_position()
        time.sleep(2.0)

        return True

    def get_move_from_cloud(self):
        """从云端获取最佳走法(不执行)"""
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

        print(f"\n最佳走法: {result['best_move']}")
        print(f"起始位置(机器人): {from_robot}")
        print(f"目标位置(机器人): {to_robot}")

        result['_from_robot'] = from_robot
        result['_to_robot'] = to_robot
        return result

    def wait_for_user_confirm(self):
        """等待用户确认后执行走棋"""
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

    def execute_from_cloud(self):
        """从云端获取最佳走法并执行(手动控制)"""
        while True:
            result = self.get_move_from_cloud()
            if result is None:
                print("获取走法失败，等待重试...")
                time.sleep(2)
                continue

            while True:
                action = self.wait_for_user_confirm()
                if action is False:
                    print("已取消走棋，等待新指令...")
                    break
                elif action == 'refresh':
                    result = self.get_move_from_cloud()
                    if result is None:
                        break
                    continue

                from_robot = result['_from_robot']
                to_robot = result['_to_robot']

                is_capture, captured = self.detect_capture(result['to_pos'])
                if is_capture:
                    print(f"检测到吃子: {captured['type']} at {result['to_display']}")

                self.execute_move(from_robot, to_robot, is_capture=is_capture)
                print("\n走棋完成，等待新指令...")
                break


def main():
    import argparse
    parser = argparse.ArgumentParser(description='机械臂走棋控制')
    parser.add_argument('--color', '-c', type=str, default='red',
                       choices=['red', 'black'],
                       help='机械臂控制方的颜色 (默认red)')
    args = parser.parse_args()

    controller = ChessArmController(arm_color=args.color)
    controller.execute_from_cloud()


if __name__ == '__main__':
    main()