#!/usr/bin/env python3
"""皮卡鱼 (Pikafish) 简单调用 - 只输出最佳走法"""
import subprocess
import time

ENGINE_PATH = "xq_src/engine/pikafish-avx2"
NNUE_PATH = "xq_src/engine/pikafish.nnue"

def send(proc, cmd):
    proc.stdin.write(cmd + "\n")
    proc.stdin.flush()

def waitfor(proc, kw, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        if kw in line:
            return True
    return False

def analyze(fen, depth=25):
    proc = subprocess.Popen(
        [ENGINE_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    send(proc, "uci")
    waitfor(proc, "uciok", 10)
    send(proc, f"setoption name EvalFile value {NNUE_PATH}")
    send(proc, "isready")
    waitfor(proc, "readyok", 10)

    send(proc, f"position fen {fen}")
    send(proc, "isready")
    waitfor(proc, "readyok", 10)

    send(proc, f"go depth {depth}")

    bestmove = None
    while True:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        if line.strip().startswith("bestmove"):
            bestmove = line.split()[1]
            break

    send(proc, "quit")
    proc.wait(timeout=5)
    return bestmove

if __name__ == "__main__":
    FEN = "rnbak1bnr/4a4/7c1/1c6p/1P2p1p2/2p6/6P1P/4C2C1/9/RNBAKABNR w"
    result = analyze(FEN, depth=25)
    print(result)
