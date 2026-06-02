# USB摄像头FEN码输出实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 camera_fen.py，通过USB摄像头实时显示棋盘，按空格捕捉帧并输出紧凑格式FEN码到终端

**Architecture:** 新建 camera_fen.py 作为入口，复用现有 ChessboardDetector，在 chessboard_detector.py 中增加 to_fen() 方法将10x9矩阵转换为FEN字符串

**Tech Stack:** OpenCV (cv2), onnxruntime, numpy

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| camera_fen.py | 新建 | 摄像头主脚本，键盘事件处理，OpenCV窗口 |
| core/chessboard_detector.py | 修改 | 增加 to_fen(board_matrix, scores) 方法 |
| core/helper_cls.py | 无操作 | 已有 dict_cate_names 映射 |

---

## 实现任务

### Task 1: 修改 ChessboardDetector 增加 to_fen() 方法

**Files:**
- Modify: `core/chessboard_detector.py:130-`

- [ ] **Step 1: 在 ChessboardDetector 类末尾添加 to_fen 方法**

```python
def to_fen(self, board_matrix: List[List[str]], scores: List[List[float]], threshold: float = 0.7) -> str:
    """
    将10x9棋子矩阵转换为紧凑格式FEN码

    @param board_matrix: 10行9列的棋子标签矩阵
    @param scores: 10行9列的置信度矩阵
    @param threshold: 置信度阈值，低于此值标记为 ?
    @return: FEN字符串 (如 "r1ba1ab1r/9/1c3c2/p3p1p1p/4c4/9/P3P1P1P/4C4/9/R1BA1AB1R")
    """
    from core.helper_cls import dict_cate_names

    fen_parts = []
    for row in range(10):
        row_chars = []
        empty_count = 0
        for col in range(9):
            piece = board_matrix[row][col]
            score = scores[row][col]

            if piece == 'point':
                empty_count += 1
            else:
                if empty_count > 0:
                    row_chars.append(str(empty_count))
                    empty_count = 0
                # 置信度低于阈值用 ? 标记
                if score < threshold:
                    row_chars.append('?')
                else:
                    row_chars.append(dict_cate_names.get(piece, '?'))

        if empty_count > 0:
            row_chars.append(str(empty_count))

        fen_parts.append(''.join(row_chars))

    return '/'.join(fen_parts)
```

- [ ] **Step 2: 验证 dict_cate_names 导入正确**

检查 core/helper_cls.py 中 dict_cate_names 已正确定义，确认 key 名称与 board_matrix 中的标签一致

Run: `python3 -c "from core.helper_cls import dict_cate_names; print(dict_cate_names)"`

- [ ] **Step 3: 提交**

```bash
git add core/chessboard_detector.py
git commit -m "feat: add to_fen() method for FEN string generation"
```

---

### Task 2: 创建 camera_fen.py 摄像头脚本

**Files:**
- Create: `camera_fen.py`

- [ ] **Step 1: 创建 camera_fen.py**

```python
#!/usr/bin/env python3
"""
USB摄像头中国象棋棋盘识别 - 输出FEN码
按 SPACE 捕捉当前帧并识别
按 ESC 退出
"""

import cv2
import numpy as np
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.chessboard_detector import ChessboardDetector


def main():
    # 模型路径
    pose_model_path = "onnx/pose/4_v6-0301.onnx"
    full_classifier_model_path = "onnx/layout_recognition/nano_v3-0319.onnx"

    # 初始化检测器
    print("正在加载模型...")
    detector = ChessboardDetector(
        pose_model_path=pose_model_path,
        full_classifier_model_path=full_classifier_model_path
    )

    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误: 无法打开摄像头")
        return

    print("摄像头已打开")
    print("按 SPACE 捕捉并识别 | 按 ESC 退出")

    window_name = "Chinese Chess Recognition - Press SPACE to capture, ESC to exit"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("错误: 无法读取摄像头帧")
            break

        # 显示画面
        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            print("退出程序")
            break
        elif key == 32:  # SPACE
            # 转换颜色空间
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 识别棋盘
            _, transformed_image, cells_labels, scores, time_info = detector.pred_detect_board_and_classifier(frame_rgb)

            if cells_labels and len(cells_labels) > 0:
                # 生成FEN码
                fen = detector.to_fen(cells_labels, scores)

                # 计算平均置信度
                avg_score = np.mean(scores) if scores else 0

                # 输出结果
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] FEN: {fen}")
                print(f"置信度: {avg_score*100:.1f}% | {time_info}")
            else:
                print("未能识别到棋盘，请调整角度后重试")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 添加执行权限**

Run: `chmod +x camera_fen.py`

- [ ] **Step 3: 测试帮助信息**

Run: `python3 camera_fen.py --help` (如果脚本支持)

---

### Task 3: 整体测试

**Files:**
- Test: `camera_fen.py` 在实际棋盘前测试

- [ ] **Step 1: 测试摄像头打开**

确保摄像头索引正确（默认0），如有问题尝试 1, 2 等

- [ ] **Step 2: 测试识别功能**

按空格后检查：
- FEN格式是否为紧凑格式
- 置信度是否正常显示
- 不确定位置是否用 `?` 标记

- [ ] **Step 3: 测试退出**

按 ESC 确认程序正常退出

---

## 验证清单

- [ ] `python3 -c "from core.chessboard_detector import ChessboardDetector; print('OK')"` 成功
- [ ] `to_fen()` 方法存在且可调用
- [ ] `camera_fen.py` 可执行
- [ ] 摄像头窗口正常显示
- [ ] 按 SPACE 输出正确格式的 FEN 码
- [ ] 按 ESC 正常退出