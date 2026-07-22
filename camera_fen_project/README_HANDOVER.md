# Camera FEN 模块交接文档

**项目:** 中国象棋棋盘识别 - USB摄像头FEN输出模块

---

## 1. 项目概述

这是一个中国象棋棋盘识别系统，通过USB摄像头实时显示棋盘，按空格键捕捉当前帧并输出棋子布局的FEN编码到终端。

### 核心功能
- 打开USB摄像头实时显示棋盘画面
- 按 SPACE 捕捉当前帧并识别棋子
- 输出紧凑格式FEN码到终端
- 按 ESC 退出程序

### 运行方式
```bash
cd camera_fen_project
python3 camera_fen.py
```

---

## 2. 文件结构

```
camera_fen_project/
├── camera_fen.py              # 主入口脚本 (USB摄像头FEN识别)
├── requirements.txt           # 依赖: opencv-python, onnxruntime
├── HISTORY.md                 # 项目历史
│
├── core/                      # 核心检测模块
│   ├── chessboard_detector.py # 主检测器类 ChessboardDetector
│   ├── helper_4_kpt.py        # 4关键点透视变换
│   ├── helper_cls.py         # 棋子类别映射 (dict_cate_names)
│   ├── kpt_4_with_xanything.py # 标注格式工具
│   └── runonnx/              # ONNX模型封装
│       ├── base_onnx.py      # ONNX基类
│       ├── rtmpose.py        # RTMPose关键点检测模型
│       └── full_classifier.py # 棋子分类模型
│
├── onnx/                      # ONNX模型文件
│   ├── pose/4_v6-0301.onnx   # 关键点检测模型 (~10MB)
│   └── layout_recognition/nano_v3-0319.onnx # 棋子分类模型 (~31MB)
│
├── resources/                 # 棋子图标 (display用)
│   ├── red_K.png, red_A.png, red_B.png, ...
│   └── black_k.png, black_a.png, black_b.png, ...
│
├── examples/                  # 示例棋盘图片
│   └── demo001.png, demo002.png, ...
│
└── docs/superpowers/          # 设计文档
    ├── specs/                 # 设计规格
    └── plans/                 # 实现计划
```

---

## 3. FEN格式说明

### 紧凑格式 (Compact FEN)

每行代表棋盘的一行（从红方视角，红方在下方），9列：

| 字符 | 含义 |
|------|------|
| 数字 1-9 | 连续的空位数 |
| K | 红帅 |
| A | 红仕 |
| B | 红象 |
| N | 红马 |
| R | 红车 |
| C | 红炮 |
| P | 红兵 |
| k | 黑将 |
| a | 黑士 |
| b | 黑象 |
| n | 黑马 |
| r | 黑车 |
| c | 黑炮 |
| p | 黑卒 |
| ? | 置信度低于阈值的不确定位置 |

**示例输出:**
```
[2026-05-17 15:00:00] FEN: r1ba1ab1r/9/1c3c2/p3p1p1p/4c4/9/P3P1P1P/4C4/9/R1BA1AB1R
置信度: 85.3% | 推理用时: 0.17s
```

---

## 4. 核心类和方法

### ChessboardDetector (core/chessboard_detector.py)

```python
class ChessboardDetector:
    def __init__(self, pose_model_path, full_classifier_model_path):
        # 初始化RTMPose关键点检测和FULL分类器

    def pred_detect_board_and_classifier(self, image_rgb) -> Tuple:
        # 检测棋盘角点 + 透视变换 + 棋子分类
        # 返回: (原图标注, 拉伸棋盘, 10x9棋子标签, 10x9置信度, 时间信息)

    def to_fen(self, board_matrix, scores, threshold=0.7) -> str:
        # 将10x9棋子矩阵转换为紧凑FEN字符串
        # 低置信度位置用 '?' 标记
```

### 关键点检测流程

```
输入图像 → RTMPose关键点检测 → 4个角点(A0, A8, J0, J8)
         → 透视变换到450x500标准棋盘
         → 棋子分类(90个位置×16类)
         → FEN输出
```

---

## 5. 已知问题 / 待改进

1. **模型文件需完整复制** - 确保 `onnx/pose/4_v6-0301.onnx` 和 `onnx/layout_recognition/nano_v3-0319.onnx` 是完整的ONNX文件（非Git LFS指针）

2. **摄像头索引** - 默认使用 `cv2.VideoCapture(0)`，如需指定其他摄像头修改 `camera_fen.py:33`

3. **置信度阈值** - 默认 `threshold=0.7`，低于此值的棋子用 `?` 标记

---

## 6. 相关文档

- `docs/superpowers/specs/2026-05-17-camera-fen-design.md` - 设计规格
- `docs/superpowers/plans/2026-05-17-camera-fen-plan.md` - 实现计划

---