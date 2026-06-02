# Chinese Chess Robot Arm System

A Chinese Chess (Xiangqi) Robot Arm System that plays autonomously against human players.

## Overview

This system implements an autonomous Chinese Chess playing robot arm system, running on Raspberry Pi 5. It uses computer vision to detect the board and pieces, combines with a UCI engine to get the best moves, and controls a DOFBOT 6-axis robot arm to complete piece grabbing and placement operations.

## System Architecture

```
┌─────────────────┐         TCP (5000)         ┌─────────────────┐
│   PC Client     │ ◄─────────────────────────► │ Raspberry Pi    │
│ chess_arm_client│        MOVE Commands         │    Server       │
└────────┬────────┘                              └────────┬────────┘
         │                                                │
         │ OpenCV + YOLO                                  │ I2C
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│  Board Detection│                              │ DOFBOT Robot Arm│
│  Piece Detection│                              │ 4x Servos (0x15)│
└─────────────────┘                              └────────┬────────┘
         │                                                │
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│   Engine Query  │                              │   Air Pump Ctrl │
│   (Pikafish)    │                              │   (GPIO Ctrl)   │
└─────────────────┘                              └─────────────────┘
```

## Hardware

| Component | Description |
|-----------|-------------|
| DOFBOT 6-axis Robot Arm | 6x bus servos, I2C address 0x15 |
| Raspberry Pi 5 | Runs server |
| PC | Runs client |
| USB Camera | Mounted on robot arm tip |
| Air Pump + GPIO Control | Piece suction |

## Quick Start

### 1. Environment Requirements

**PC (Client):**
- Python 3.8+
- OpenCV
- NumPy

**Raspberry Pi (Server):**
- Python 3.8+
- OpenCV
- NumPy
- RPi.GPIO
- smbus2

### 2. Install Dependencies

```bash
# PC
pip install opencv-python numpy

# Raspberry Pi
pip install opencv-python numpy RPi.GPIO smbus2
```

### 3. Start Server (Raspberry Pi)

```bash
python chess_arm_server.py --port 5000
```

### 4. Start Client (PC)

Red side (first move):
```bash
python chess_arm_client.py --host 192.168.137.60 --color red
```

Black side (second move):
```bash
python chess_arm_client.py --host 192.168.137.60 --color black
```

### 5. Client Controls

| Key | Action |
|-----|--------|
| `r` | Detect board and get move |
| `g` | Execute move |
| `q` | Cancel and quit |
| `r` (during confirmation) | Refresh and redetect board |

## Directory Structure

```
chinese_chess_robot/
├── chess_arm_server.py    # Server (Raspberry Pi)
├── chess_arm_client.py    # Client (PC)
├── cloud_query.py         # Cloud query
├── simple_engine.py       # Local engine interface (Pikafish)
├── board_detector.py      # Board detection
├── piece_detector.py      # Piece detection & FEN generation
├── board_to_robot.py      # Board to robot coordinate conversion
├── coord_utils.py         # UCCI coordinate utilities
├── ik.py                  # Inverse kinematics solver
├── air_pump.py            # Air pump control
├── Arm_Lib/               # Robot arm SDK
├── engine/                # Pikafish engine
├── config/                # Configuration files
│   ├── camera_config.json
│   ├── board_calibration.json
│   └── board_robot_coords.json
├── 开发文档.md            # Development documentation (Chinese)
├── 交接文档.md            # Handover documentation (Chinese)
└── CLAUDE.md              # Development guide
```

## Configuration

### IP Address

Server default IP: `192.168.137.60`

To modify, edit line 220 in `chess_arm_client.py`:
```python
default='192.168.137.60'
```

### Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Piece height | 5cm | Piece grab height |
| First descent height | 8cm | Prevent direct descent causing piece displacement |
| Safe height | 15cm | Robot arm movement safe height |
| Z-axis correction factor | 0.15 | Compensate height error at different positions |
| Column spacing | 3.1cm | |
| Row spacing | 2.85cm | |
| Chu River Han Pass | 2.2cm | |

### Z-axis Correction Formula

```
z_corrected = z + 0.15 * sqrt(x^2 + y^2)
```

## Network Protocol

Server listens on port 5000, accepts the following commands:

| Command | Description |
|---------|-------------|
| `MOVE,x_from,y_from,z_from,x_to,y_to,z_to,is_capture,move_desc` | Move piece |
| `HOME` | Return to home position |
| `PUMP_ON` | Turn on air pump |
| `PUMP_OFF` | Turn off air pump |
| `QUIT` | Disconnect |

Example:
```
MOVE,-12.4,28.0,5,-9.3,28.0,5,false,
MOVE,-12.4,28.0,5,-9.3,28.0,5,true,马
```

## Troubleshooting

### Connection Failed
```bash
# Check network connectivity
ping 192.168.137.60

# Check if port is open
nc -zv 192.168.137.60 5000
```

### Coordinate Errors
- Check origin settings in `board_to_robot.py`
- Verify `rotate_move_180` correctly handles black side
- Compare displayed coordinates with actual board positions

### IK No Solution
- Check if target coordinates are within robot arm working range
- Adjust `z_correction_factor` parameter
- Verify IK parameter configuration

### Piece Suction Failed
- Check if air pump is working properly
- Verify GPIO wiring
- Confirm suction height is correct

## Related Documentation

- [开发文档.md](开发文档.md) - Detailed technical documentation (Chinese)