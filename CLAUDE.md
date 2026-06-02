# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

中国象棋机械臂对弈系统，运行在树莓派5上。系统通过计算机视觉检测棋盘和棋子，通过云端引擎获取最佳走法，然后控制机械臂执行走棋动作。

## 系统架构

```
电脑 (chess_arm_client.py)
    ↓ TCP (端口5000)
树莓派 (chess_arm_server.py)
    ↓ I2C
机械臂 (6个总线舵机, 地址0x15)
    ↓
气泵 (吸取棋子)
```

## 文件说明

| 文件 | 功能 |
|------|------|
| `chess_arm_server.py` | 树莓派服务器，监听TCP并执行机械臂动作 |
| `chess_arm_client.py` | 电脑客户端，检测棋盘并发送走法 |
| `cloud_query.py` | 调用引擎获取最佳走法 |
| `board_detector.py` | 棋盘检测 (9x10格) |
| `piece_detector.py` | 棋子检测与FEN生成 |
| `board_to_robot.py` | 棋盘坐标转机器人坐标 |
| `coord_utils.py` | UCCI坐标转换工具 |
| `ik.py` | 逆运动学求解器 |
| `simple_engine.py` | 本地引擎调用 (Pikafish) |
| `air_pump.py` | 气泵控制 |
| `Arm_Lib/` | 机械臂SDK |

## 关键参数

| 参数 | 值 |
|------|---|
| 棋子高度 | 5cm |
| 一次下降高度 | 8cm |
| 安全高度 | 15cm |
| Z轴校正系数 | 0.15 |
| 初始位置 | [179, 179, 0, 0, 90, 65] |

## 运行命令

```bash
# 树莓派上启动服务器
python xq_ws/chess_arm_server.py --port 5000

# 电脑上启动客户端 (红方)
python xq_ws/chess_arm_client.py --host 192.168.137.60 --color red

# 电脑上启动客户端 (黑方)
python xq_ws/chess_arm_client.py --host 192.168.137.60 --color black
```

## 机械臂控制 (Arm_Lib.py)

`Arm_Device` class on I2C address `0x15`:
- `Arm_serial_servo_write(id, angle, time)` — 单个舵机
- `Arm_serial_servo_write6(s1-s6, time)` — 6个舵机同时控制
- `Arm_serial_set_torque(onoff)` — 使能/失能扭矩

## 坐标系统

- 棋盘: 9列 x 10行
- 坐标格式: UCCI (a0-i9)
- 棋盘原点: [-12.4, 28.0, 2.0] cm
- 列间距: 3.1cm, 行间距: 2.85cm, 楚河汉界: 2.2cm

## 走棋流程

1. 客户端检测棋盘，生成FEN
2. 调用引擎获取最佳走法
3. 坐标转换后发送MOVE命令
4. 服务器执行:
   - 初始位置 → 起始位置上方(安全高度)
   - 一次下降(8cm) → 二次下降(棋子高度5cm)
   - 吸取 → 抬升
   - 移动到目标位置上方 → 一次下降 → 二次下降
   - 放置 → 抬升到安全高度 → 初始位置

## Z轴校正

公式: `z_corrected = z + k * sqrt(x^2 + y^2)`

其中 k = 0.15，用于校正不同位置的高度误差。

## 注意事项

- 红方视角: FEN中大写字母为红方
- 黑方视角: 坐标需要旋转180度处理
- 吃子判定使用原始FEN坐标，不经过旋转
