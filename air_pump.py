#!/usr/bin/env python3
"""
气泵控制模块
通过GPIO控制气泵的通断
支持Raspberry Pi (RPi.GPIO或lgpio)
"""

try:
    import lgpio as GPIO
    IS_LGPIO = True
    IS_RPI = True
except ImportError:
    IS_LGPIO = False
    try:
        import RPi.GPIO as GPIO
        IS_RPI = True
    except ImportError:
        IS_RPI = False
        print("警告: 非Raspberry Pi环境,GPIO控制不可用")


class AirPump:
    """气泵控制器"""

    def __init__(self, gpio_pin=18):
        """
        初始化气泵控制

        Args:
            gpio_pin: GPIO引脚编号,默认18
        """
        self.gpio_pin = gpio_pin
        self.is_active = False
        self._chip = None

        if IS_LGPIO:
            self._chip = GPIO.gpiochip_open(0)
            GPIO.gpio_claim_output(self._chip, self.gpio_pin)
            print(f"气泵初始化完成 (lgpio), GPIO引脚: {self.gpio_pin}")
        elif IS_RPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.OUT)
            print(f"气泵初始化完成 (RPi.GPIO), GPIO引脚: {self.gpio_pin}")
        else:
            print("模拟模式: 气泵控制(GPIO不可用)")

    def activate(self):
        """开启气泵(吸气吸起棋子)"""
        if IS_LGPIO and self._chip:
            GPIO.gpio_write(self._chip, self.gpio_pin, 1)
        elif IS_RPI:
            GPIO.output(self.gpio_pin, GPIO.HIGH)
        self.is_active = True
        print("气泵: 开启")

    def deactivate(self):
        """关闭气泵(放气放下棋子)"""
        if IS_LGPIO and self._chip:
            GPIO.gpio_write(self._chip, self.gpio_pin, 0)
        elif IS_RPI:
            GPIO.output(self.gpio_pin, GPIO.LOW)
        self.is_active = False
        print("气泵: 关闭")

    def is_activated(self):
        """返回气泵当前状态"""
        return self.is_active

    def cleanup(self):
        """清理GPIO资源"""
        if IS_LGPIO and self._chip:
            GPIO.gpiochip_close(self._chip)
            print("气泵 (lgpio) GPIO已清理")
        elif IS_RPI:
            GPIO.cleanup(self.gpio_pin)
            print("气泵 (RPi.GPIO) GPIO已清理")


class AirPumpSimulator:
    """气泵模拟器(用于非Raspberry Pi环境测试)"""

    def __init__(self):
        self.is_active = False
        print("气泵模拟器初始化")

    def activate(self):
        """模拟开启"""
        self.is_active = True
        print("气泵[模拟]: 开启")

    def deactivate(self):
        """模拟关闭"""
        self.is_active = False
        print("气泵[模拟]: 关闭")

    def is_activated(self):
        return self.is_active


def create_air_pump(gpio_pin=18):
    """创建气泵控制器"""
    if IS_RPI:
        return AirPump(gpio_pin)
    else:
        return AirPumpSimulator()


if __name__ == '__main__':
    pump = create_air_pump()

    print("\n测试序列: 开启 -> 等待2秒 -> 关闭")
    pump.activate()
    import time
    time.sleep(2)
    pump.deactivate()

    if IS_RPI:
        pump.cleanup()