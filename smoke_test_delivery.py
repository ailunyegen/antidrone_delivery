"""交付包冒烟测试：验证某个 `antidrone_delivery 提交版_XX` 目录可独立运行。

用法:
    python smoke_test_delivery.py                      # 自动选版本号最高的交付包
    python smoke_test_delivery.py --package "..\\antidrone_delivery 提交版_05"
    python smoke_test_delivery.py --cloud              # 额外验证走 config.json 的云端管线
    python smoke_test_delivery.py --keep               # 保留 result/ 产物便于排查

检查项:
    1. 交付包自检：无 config.json / 无平台标签 .pyd / 无 __pycache__ / 无 .bak / 无 .c
    2. Tier1 零 LLM 应急预案（--fast-first --iterations 0）：exit 0 且有 mission_success
    3. 前端模块自检（main_compiled.py --check）：5/5 已编译
    4. --cloud：临时放入仓库 config.json，跑一次单候选云端管线，校验
       full_result.json 的 llm_backend.api_mode 为 cloud-json，跑完删除临时 config.json

注意：本脚本会在交付包目录内写入（result/、临时 config.json），交付包通常位于
工作区之外，因此在本机 DSH 沙箱下运行需要更宽的文件权限。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent

FAILURES: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(label)
        print(f"  [FAIL] {label} {detail}")


def pick_package(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_dir():
            raise SystemExit(f"交付包目录不存在: {path}")
        return path
    candidates = []
    for child in PARENT.glob("antidrone_delivery 提交版_*"):
        if child.is_dir():
            suffix = child.name.rsplit("_", 1)[-1]
            candidates.append((suffix, child))
    if not candidates:
        raise SystemExit(f"在 {PARENT} 下找不到任何交付包目录，请用 --package 指定")
    candidates.sort()
    return candidates[-1][1].resolve()


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def extract_metric(stdout: str, key: str) -> str | None:
    for line in stdout.splitlines():
        line = line.strip().rstrip(",")
        if line.startswith(f'"{key}"'):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="交付包冒烟测试")
    parser.add_argument("--package", default=None, help="交付包目录（默认自动选最高版本）")
    parser.add_argument("--cloud", action="store_true", help="额外验证云端管线（需要 config.json）")
    parser.add_argument("--keep", action="store_true", help="保留 result/ 产物")
    args = parser.parse_args()

    package = pick_package(args.package)
    print(f"== 交付包冒烟测试: {package.name} ==")

    # ── 1. 包自检 ──
    print("\n-- 包内容自检 --")
    check(not (package / "config.json").exists(), "不含 config.json（真实 Key）")
    check(not list(package.rglob("*.cp312-win_amd64.pyd")), "不含平台标签 .pyd")
    check(not list(package.rglob("__pycache__")), "不含 __pycache__")
    check(not list(package.rglob("*.bak")), "不含 .bak")
    check(not list(package.rglob("*.c")), "不含 Cython 中间文件 .c")
    check((package / "military_research" / "engine.pyd").is_file(), "engine.pyd 存在")

    # ── 2. Tier1 零 LLM ──
    print("\n-- Tier1 零 LLM 应急预案 --")
    proc = run(
        [sys.executable, "run_military_research.py", "--scenario", "data/sample_antidrone.json",
         "--fast-first", "--iterations", "0", "--sim-runs", "1", "--output-dir", "result/smoke_tier1"],
        package,
    )
    check(proc.returncode == 0, "Tier1 退出码为 0", (proc.stderr or "")[-200:])
    mission_success = extract_metric(proc.stdout, "mission_success")
    check(mission_success is not None, "Tier1 输出含 mission_success")
    if mission_success:
        print(f"        mission_success = {mission_success}")

    # ── 3. 前端自检 ──
    print("\n-- 前端模块自检 --")
    proc = run([sys.executable, "main_compiled.py", "--check"], package, timeout=180)
    ok_count = proc.stdout.count("[OK]")
    check(ok_count >= 5, f"main_compiled.py --check 通过 5/5（实测 {ok_count}）", (proc.stderr or "")[-200:])

    # ── 4. 可选：云端管线 ──
    if args.cloud:
        print("\n-- 云端管线（临时 config.json）--")
        config_src = HERE / "config.json"
        if not config_src.is_file():
            check(False, "仓库 config.json 存在（--cloud 需要它）")
        else:
            shutil.copy2(config_src, package / "config.json")
            try:
                proc = run(
                    [sys.executable, "run_military_research.py", "--scenario", "data/sample_antidrone.json",
                     "--iterations", "1", "--single-candidate", "--sim-runs", "1",
                     "--output-dir", "result/smoke_cloud"],
                    package,
                )
                check(proc.returncode == 0, "云端管线退出码为 0", (proc.stderr or "")[-300:])
                manifest_path = package / "result" / "smoke_cloud" / "full_result.json"
                if manifest_path.is_file():
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    backend = manifest.get("llm_backend", {})
                    check("cloud-json" in str(backend.get("api_mode", "")),
                          "运行清单记录 cloud-json 后端", str(backend))
                    print(f"        api_mode={backend.get('api_mode')} model={backend.get('model_id')} "
                          f"source={backend.get('source')}")
                else:
                    check(False, "生成 full_result.json")
            finally:
                (package / "config.json").unlink(missing_ok=True)

    # ── 收尾 ──
    if not args.keep:
        shutil.rmtree(package / "result", ignore_errors=True)
    for cache in package.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    print("\n== 结果 ==")
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
