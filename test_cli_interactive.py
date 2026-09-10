"""命令行交互模式（使用方式 5.1）自测：用桩客户端跑完整流程，不需要 LLM 与 API Key。

背景：交互模式保存方案时曾调用已被重构删除的旧参数，跑到保存步骤必然 TypeError。
本测试用桩 client + 预置 stdin 驱动 `run_interactive` 走完全程，断言 JSON 产物正确。

用法:
    python test_cli_interactive.py
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"

STUB_PLAN = """1. 侦察预警阶段
使用JY-17B低空搜索雷达与T1北部BC波段补盲雷达建立空情态势。

2. 电子压制阶段
T1定向干扰端A对无人机C2链路实施压制。

3. 拦截打击阶段
天猎-1拦截无人机实施拦截，T1网捕站对低空慢速目标实施网捕。
"""

FAILURES: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(label)
        print(f"  [FAIL] {label} {detail}")


class StubClient:
    """最小桩：只实现交互流程用到的属性与方法。"""

    model = "stub-model"
    provider = "stub"

    def generate_stream(self, prompt: str, max_tokens: int = 8000):
        yield STUB_PLAN


def main() -> int:
    import main_compiled

    print("== 交互模式自测（桩客户端）==")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

    # 5 个交互提示全部直接回车 -> 走默认值（任务/态势/资源/硬约束/软约束）
    stdin_backup = sys.stdin
    sys.stdin = io.StringIO("\n\n\n\n\n")
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            main_compiled.run_interactive(StubClient())
    except Exception as exc:  # noqa: BLE001 - 测试就是要把异常暴露出来
        check(False, "交互流程无异常", f"{type(exc).__name__}: {exc}")
    finally:
        sys.stdin = stdin_backup

    produced = sorted(OUTPUT_DIR.glob("plan_*.json")) if OUTPUT_DIR.exists() else []
    check(len(produced) == 3, f"生成 3 份方案 JSON（实测 {len(produced)}）")
    if not produced:
        print("\n== 结果 ==\n失败: 没有产物")
        return 1

    for path in produced:
        data = json.loads(path.read_text(encoding="utf-8"))
        ok_keys = list(data.keys()) == [
            "planId", "planName", "targetName", "generateTime", "actionCount", "actions"
        ]
        check(ok_keys, f"{path.name} 顶层键符合骨架")
        check(data["actionCount"] == len(data["actions"]) >= 1,
              f"{path.name} actionCount 与 actions 一致（{data['actionCount']}）")
        ids = [a["resourceId"] for a in data["actions"]]
        check(len(ids) == len(set(ids)), f"{path.name} 装备不重复")
        check(all(len(a) == 6 for a in data["actions"]), f"{path.name} action 字段数为 6")

    check(not list(OUTPUT_DIR.glob("plan_*.txt")), "不再产生 .txt 输出")

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

    print("\n== 结果 ==")
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
