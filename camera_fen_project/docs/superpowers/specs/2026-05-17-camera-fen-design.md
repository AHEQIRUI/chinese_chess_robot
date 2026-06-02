# USB摄像头FEN码输出功能设计

**日期:** 2026-05-17
**项目:** Chinese Chess Recognition
**方案:** A - 新建独立脚本 camera_fen.py

## 概述

创建一个命令行工具，通过USB摄像头实时显示棋盘画面，用户按空格键捕捉当前帧，程序输出紧凑格式FEN码到终端。

## 技术架构

```
camera_fen.py (新文件)
├── cv2.VideoCapture(0)          # 打开USB摄像头
├── cv2.imshow()                 # 显示实时画面
├── 键盘事件处理                 # SPACE=识别, ESC=退出
└── ChessboardDetector            # 复用现有检测器

core/chessboard_detector.py (修改)
├── 新增 to_fen(board_matrix)   # 10x9矩阵 → FEN字符串
└── 返回含 `?` 的不确定标记

core/helper_cls.py (确认)
└── 类别 → FEN字符映射表
```

## 详细设计

### 1. FEN格式（紧凑格式）

行列方向：从红方视角（下方）开始
- 第1行 = 红方底线（帅/车等）
- 第10行 = 黑方底线（将/车等）

字符映射：
| 类别 | FEN |
|------|-----|
| red_king | R |
| red_advisor | A |
| red_bishop | B |
| red_knight | N |
| red_rook | R |
| red_cannon | C |
| red_pawn | P |
| black_king | r |
| black_advisor | a |
| black_bishop | b |
| black_knight | n |
| black_rook | r |
| black_cannon | c |
| black_pawn | p |
| point | 数字(空位数) |
| other | ? |

### 2. 摄像头脚本行为

```
启动摄像头
显示实时窗口 "Chinese Chess - Press SPACE to capture, ESC to exit"

主循环:
  读取帧
  显示画面
  检测按键:
    - SPACE: 捕捉当前帧 → 识别 → 输出FEN
    - ESC: 退出程序
```

### 3. FEN输出格式

每行输出:
```
[时间戳] FEN: r1ba1ab1r/9/1c3c2/p3p1p1p/4c4/9/P3P1P1P/4C4/9/R1BA1AB1R
置信度: XX%
```

### 4. 不确定位置标记

当分类置信度 < 0.7 时，该位置用 `?` 替代真实字符。

### 5. 依赖

- OpenCV (cv2)
- 现有 core 模块（不修改 app.py）

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| camera_fen.py | 新建 | 摄像头入口脚本 |
| core/chessboard_detector.py | 修改 | 增加 to_fen() 方法 |
| docs/superpowers/specs/YYYY-MM-DD-camera-fen-design.md | 新建 | 本文档 |

## 测试场景

1. 摄像头正确打开，显示实时画面
2. 按SPACE后正确输出FEN码
3. 按ESC正确退出
4. FEN格式正确（紧凑格式）
5. 不确定位置用 `?` 标记