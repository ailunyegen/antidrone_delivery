"""
军事研究仿真引擎 - 命令行入口 (pyd 编译版)

用法:
    python run_military_research.py --scenario data/sample_joint_operation.json
    python run_military_research.py --help

本文件是 military_research/cli.pyd 的薄包装，源代码已编译为动态链接库。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from military_research.cli import main

if __name__ == "__main__":
    main()
