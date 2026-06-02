#!/usr/bin/env python3
"""
中国象棋坐标转换工具
数字坐标 (col, row) <-> 字母数字坐标 (a0, i9)
"""


def numeric_to_ucci(col, row):
    """
    将数字坐标转换为UCCI格式

    Args:
        col: 列 (0-8)
        row: 行 (0-9) - 内部坐标: row 0 = 红方底线

    Returns:
        str: 如 'a9', 'i0' (row 0 显示为 9, row 9 显示为 0)
    """
    if 0 <= col <= 8 and 0 <= row <= 9:
        return f"{chr(ord('a') + col)}{9 - row}"
    return "???"


def ucci_to_numeric(ucci_str):
    """
    将UCCI格式转换为数字坐标

    Args:
        ucci_str: 如 'a9', 'i0' - 显示坐标

    Returns:
        tuple: (col, row) 内部坐标 - row 0 = 红方底线
    """
    if len(ucci_str) != 2:
        return None
    col = ord(ucci_str[0].lower()) - ord('a')
    try:
        row_display = int(ucci_str[1])
        row = 9 - row_display
        if 0 <= col <= 8 and 0 <= row <= 9:
            return (col, row)
    except ValueError:
        pass
    return None


def format_move(from_col, from_row, to_col, to_row):
    """
    格式化走棋为UCCI字符串

    Args:
        from_col, from_row: 起始位置
        to_col, to_row: 目标位置

    Returns:
        str: 如 'a0i9'
    """
    return numeric_to_ucci(from_col, from_row) + numeric_to_ucci(to_col, to_row)


def parse_move(move_str):
    """
    解析UCCI走法字符串

    Args:
        move_str: 如 'a0i9'

    Returns:
        tuple: ((from_col, from_row), (to_col, to_row)) 或 None
    """
    if len(move_str) != 4:
        return None
    from_pos = ucci_to_numeric(move_str[:2])
    to_pos = ucci_to_numeric(move_str[2:])
    if from_pos and to_pos:
        return (from_pos, to_pos)
    return None


def uci_to_numeric(uci_str):
    """
    将UCI格式(国际象棋)转换为数字坐标
    e.g., 'e2' -> (4, 1), 'g1' -> (6, 0)

    Args:
        uci_str: 如 'e2', 'g1' (col a-h, row 1-8)

    Returns:
        tuple: (col, row) 内部坐标 - col 0=a, row 0=rank1
    """
    if len(uci_str) != 2:
        return None
    col = ord(uci_str[0].lower()) - ord('a')
    try:
        row = int(uci_str[1]) - 1
        if 0 <= col <= 7 and 0 <= row <= 7:
            return (col, row)
    except ValueError:
        pass
    return None


def numeric_to_uci(col, row):
    """
    将数字坐标转换为UCI格式(国际象棋)
    e.g., (4, 1) -> 'e2', (6, 0) -> 'g1'

    Args:
        col: 列 (0-7)
        row: 行 (0-7) - row 0 = rank1

    Returns:
        str: 如 'e2'
    """
    if 0 <= col <= 7 and 0 <= row <= 7:
        return f"{chr(ord('a') + col)}{row + 1}"
    return "???"


def uci_to_ucci(uci_str):
    """
    将UCI格式(国际象棋)转换为UCCI格式(中国象棋)
    e.g., 'e2' -> 'e4' (红方视角, row要转换)

    Args:
        uci_str: 如 'e2'

    Returns:
        str: UCCI格式 如 'e4'
    """
    pos = uci_to_numeric(uci_str)
    if pos is None:
        return None
    col, row = pos
    return numeric_to_ucci(col, row)


def parse_uci_move(move_str):
    """
    解析UCI走法字符串(国际象棋)
    e.g., 'g2f3' -> ((6, 1), (5, 2))

    Args:
        move_str: 如 'g2f3'

    Returns:
        tuple: ((from_col, from_row), (to_col, to_row)) 或 None
    """
    if len(move_str) != 4:
        return None
    from_pos = uci_to_numeric(move_str[:2])
    to_pos = uci_to_numeric(move_str[2:])
    if from_pos and to_pos:
        return (from_pos, to_pos)
    return None


def ucci_to_uci(ucci_str):
    """
    将UCCI格式(中国象棋)转换为UCI格式(国际象棋)
    仅用于坐标形式转换，不做棋种转换
    e.g., 'c3' -> 'c3' (列相同, 行转换)

    Args:
        ucci_str: 如 'c3'

    Returns:
        str: UCI格式 如 'c3'
    """
    if len(ucci_str) != 2:
        return None
    col = ucci_str[0].lower()
    try:
        row_display = int(ucci_str[1])
        row = 9 - row_display
        if 0 <= row <= 9:
            return f"{col}{row + 1}"
    except ValueError:
        pass
    return None


if __name__ == '__main__':
    # 测试
    print("坐标转换测试: (0,0) = a9")
    print(f"  numeric_to_ucci(0, 0) = {numeric_to_ucci(0, 0)}")
    print(f"  numeric_to_ucci(4, 5) = {numeric_to_ucci(4, 5)}")
    print(f"  numeric_to_ucci(8, 9) = {numeric_to_ucci(8, 9)}")
    print(f"  ucci_to_numeric('a9') = {ucci_to_numeric('a9')}")
    print(f"  ucci_to_numeric('i0') = {ucci_to_numeric('i0')}")
    print(f"  format_move(0, 0, 8, 9) = {format_move(0, 0, 8, 9)}")
    print(f"  parse_move('h2e2') = {parse_move('h2e2')}")