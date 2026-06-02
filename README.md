# 中国象棋机械臂对弈系统

A Chinese Chess (Xiangqi) Robot Arm System that plays autonomously against human players.

## 项目简介

本系统实现了一个能够自主下中国象棋的机械臂对弈系统，可以运行在树莓派5上。通过计算机视觉检测棋盘和棋子，结合 UCI 引擎获取最佳走法，控制 DOFBOT 6轴机械臂完成抓取和放置棋子等操作。

## 系统架构

```
┌─────────────────┐         TCP (5000)         ┌─────────────────┐
│   电脑客户端     │ ◄─────────────────────────► │   树莓派服务器   │
│ chess_arm_client│        MOVE 指令            │ chess_arm_server│
└────────┬────────┘                              └────────┬────────┘
         │                                                │
         │ OpenCV + YOLO                                  │ I2C
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│   棋盘检测      │                              │   DOFBOT 机械臂  │
│   棋子识别      │                              │   4轴舵机 (0x15) │
└─────────────────┘                              └────────┬────────┘
         │                                                │
         │                                               │
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│   引擎调用      │                              │     气泵控制    │
│  (Pikafish)     │                              │   (GPIO 控制)    │
└─────────────────┘                              └─────────────────┘
```

## 硬件清单

| 组件 | 说明 |
|------|------|
| DOFBOT 6轴机械臂 | 6个总线舵机, I2C地址 0x15 |
| 树莓派5 | 运行服务器 |
| 电脑 | 运行客户端 |
| USB相机 | 安装在机械臂末端 |
| 气泵 + GPIO控制 | 吸取棋子 |

## 快速开始

### 1. 环境要求

**电脑端 (客户端):**
- Python 3.8+
- OpenCV
- NumPy

**树莓派端 (服务器):**
- Python 3.8+
- OpenCV
- NumPy
- RPi.GPIO
- smbus2

### 2. 安装依赖

```bash
# 电脑端
pip install opencv-python numpy

# 树莓派端
pip install opencv-python numpy RPi.GPIO smbus2
```

### 3. 启动服务器 (树莓派)

```bash
python chess_arm_server.py --port 5000
```

### 4. 启动客户端 (电脑)

红方 (先手):
```bash
python chess_arm_client.py --host 192.168.137.60 --color red
```

黑方 (后手):
```bash
python chess_arm_client.py --host 192.168.137.60 --color black
```

### 5. 客户端操作

| 按键 | 功能 |
|------|------|
| `r` | 检测棋盘，获取走法 |
| `g` | 执行走棋 |
| `q` | 取消并退出 |
| `r` (等待确认时) | 刷新重新检测 |

## 目录结构

```
chinese_chess_robot/
├── chess_arm_server.py    # 服务器 (树莓派)
├── chess_arm_client.py    # 客户端 (电脑)
├── cloud_query.py         # 引擎调用
├── simple_engine.py       # 本地引擎接口 (Pikafish)
├── board_detector.py      # 棋盘检测
├── piece_detector.py      # 棋子检测与FEN生成
├── board_to_robot.py      # 棋盘坐标转机器人坐标
├── coord_utils.py         # UCCI坐标转换工具
├── ik.py                  # 逆运动学求解器
├── air_pump.py            # 气泵控制
├── Arm_Lib/               # 机械臂SDK
├── engine/                # Pikafish引擎
├── config/                # 配置文件
│   ├── camera_config.json
│   ├── board_calibration.json
│   └── board_robot_coords.json
├── 开发文档.md            # 详细技术文档
├── 交接文档.md            # 项目交接文档
└── CLAUDE.md              # 开发指南
```

## 配置说明

### IP地址配置

服务器默认 IP: `192.168.137.60`

如需修改，编辑 `chess_arm_client.py` 第220行:
```python
default='192.168.137.60'
```

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 棋子高度 | 5cm | 棋子抓取高度 |
| 一次下降高度 | 8cm | 避免直接下降导致棋子移位 |
| 安全高度 | 15cm | 机械臂移动安全高度 |
| Z轴校正系数 | 0.15 | 补偿不同位置的高度误差 |
| 列间距 | 3.1cm | |
| 行间距 | 2.85cm | |
| 楚河汉界 | 2.2cm | |

### Z轴校正公式

```
z_corrected = z + 0.15 * sqrt(x^2 + y^2)
```

## 网络协议

服务器监听端口 5000，接收以下命令:

| 命令 | 说明 |
|------|------|
| `MOVE,x_from,y_from,z_from,x_to,y_to,z_to,is_capture,move_desc` | 移动棋子 |
| `HOME` | 返回初始位置 |
| `PUMP_ON` | 气泵开启 |
| `PUMP_OFF` | 气泵关闭 |
| `QUIT` | 断开连接 |

示例:
```
MOVE,-12.4,28.0,5,-9.3,28.0,5,false,
MOVE,-12.4,28.0,5,-9.3,28.0,5,true,马
```

## 故障排查

### 连接失败
```bash
# 检查网络连通性
ping 192.168.137.60

# 检查端口是否开放
nc -zv 192.168.137.60 5000
```

### 坐标错误
- 检查 `board_to_robot.py` 中的原点设置
- 验证 `rotate_move_180` 是否正确处理黑方
- 对比显示坐标与实际棋盘位置

### IK无解
- 检查目标坐标是否在机械臂工作范围内
- 调整 `z_correction_factor` 参数
- 验证IK参数配置

### 棋子吸取失败
- 检查气泵是否正常工作
- 验证GPIO接线
- 确认吸取高度是否正确

## 相关文档

- [开发文档.md](开发文档.md) - 详细技术文档


