"""
将 military_research/ 包编译为 .pyd 动态链接库

用法:
    python build_military_pyd.py              # 编译全部 .py → .pyd
    python build_military_pyd.py --clean      # 删除已编译的 .pyd 和中间文件
    python build_military_pyd.py --dry-run    # 仅列出待编译模块，不实际编译

依赖:
    pip install cython setuptools
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PACKAGE_DIR = _HERE / "military_research"
_BUILD_DIR = Path(tempfile.mkdtemp(prefix="pyd_"))

# 不编译的模块（纯入口/无业务逻辑）
_SKIP_MODULES = {"__init__"}


def find_modules(package_dir: Path) -> list[Path]:
    """返回所有需要编译的 .py 模块路径，排除 __init__.py"""
    py_files = sorted(package_dir.glob("*.py"))
    return [f for f in py_files if f.stem not in _SKIP_MODULES]


def clean(package_dir: Path, build_dir: Path) -> None:
    """删除所有 .pyd、.c 中间文件及编译目录"""
    removed = 0
    for pyd in package_dir.glob("*.pyd"):
        pyd.unlink()
        print(f"  删除: {pyd}")
        removed += 1
    for c_file in package_dir.glob("*.c"):
        c_file.unlink()
        print(f"  删除: {c_file}")
        removed += 1
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print(f"  删除: {build_dir}")
    print(f"\n共清理 {removed} 个文件 + 1 个编译目录")


def compile_modules(modules: list[Path], package_dir: Path, build_dir: Path) -> None:
    """逐文件独立编译: cython → .c → .pyd，避免 Windows 260 字符路径限制"""
    import subprocess
    from setuptools import setup

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)

    total = len(modules)
    success = 0

    for i, py_path in enumerate(modules):
        stem = py_path.stem
        print(f"\n[{i+1}/{total}] 编译 {stem}...")

        # Step 1: Cython .py → .c (输出到短临时目录)
        c_file = build_dir / f"{stem}.c"
        result = subprocess.run(
            [
                sys.executable, "-m", "cython",
                "-3",
                str(py_path),
                "-o", str(c_file),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            print(f"  [FAIL] Cython: {result.stderr[:300]}")
            continue

        # Step 2: 编译 .c → .pyd (输出到 build_dir)
        module_name = f"military_research.{stem}"
        try:
            setup(
                name=f"build_{stem}",
                ext_modules=cythonize_single(module_name, c_file, build_dir),
                script_args=[
                    "build_ext",
                    "--inplace",
                    f"--build-lib={build_dir}",
                    f"--build-temp={build_dir / 'temp'}",
                ],
            )
        except SystemExit as e:
            if e.code not in (0, None):
                print(f"  [FAIL] build_ext exit {e.code}")
                continue

        # Step 3: 移动 .pyd 到 package_dir 并重命名为裸名
        built = None
        for pyd in build_dir.glob(f"{stem}*.pyd"):
            built = pyd
            break
        if built is None:
            # 可能在子目录
            for pyd in build_dir.rglob(f"{stem}*.pyd"):
                built = pyd
                break

        if built is None:
            print(f"  [FAIL] .pyd not found")
            continue

        dest = package_dir / f"{stem}.pyd"
        if dest.exists():
            dest.unlink()
        shutil.move(str(built), str(dest))
        print(f"  [OK] {stem}.pyd")

        # 清理 .c 文件
        if c_file.exists():
            c_file.unlink()

        success += 1

    print(f"\n编译完成: {success}/{total} 个 .pyd 文件已生成")


def cythonize_single(module_name: str, c_file: Path, build_dir: Path):
    """为单个 .c 文件创建 Extension 并 Cythonize"""
    from Cython.Build import cythonize
    from setuptools import Extension as _Ext
    ext = _Ext(name=module_name, sources=[str(c_file)])
    return cythonize(
        [ext],
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        },
        build_dir=str(build_dir / "cy"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="编译 military_research/ 为 .pyd")
    parser.add_argument("--clean", action="store_true", help="清理所有 .pyd 和中间文件")
    parser.add_argument("--dry-run", action="store_true", help="仅列出待编译模块")
    parser.add_argument("--yes", action="store_true", help="跳过确认提示（非交互模式）")
    args = parser.parse_args()

    if args.clean:
        clean(_PACKAGE_DIR, _BUILD_DIR)
        return

    modules = find_modules(_PACKAGE_DIR)

    if not modules:
        print("未找到需要编译的 .py 模块")
        return

    print(f"将编译 {len(modules)} 个模块:")
    for f in modules:
        print(f"  {f.relative_to(_HERE)}")
    print(f"保留 __init__.py 作为包入口")

    if args.dry_run:
        print("\n(dry-run 模式，未执行编译)")
        return

    # 确认
    if not args.yes:
        print("\n按 Enter 开始编译，或 Ctrl+C 取消...")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print("\n已取消")
            sys.exit(0)

    compile_modules(modules, _PACKAGE_DIR, _BUILD_DIR)

    # 编译后验证
    print("\n验证导入...")
    sys.path.insert(0, str(_HERE))
    try:
        from military_research.domain import Scenario
        from military_research.case_memory import CaseBank
        from military_research.engine import MilitaryResearchPipeline
        print("  [OK] all core imports successful")
    except Exception as exc:
        print(f"  [FAIL] import verification: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
