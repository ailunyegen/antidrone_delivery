"""
核心模块导入兼容层
自动检测并导入编译后的.pyd模块，如果不存在则回退到.py源码导入

使用方法:
    在需要使用核心模块的地方，替换原来的导入语句:

    原来的导入:
        from scenario_builder import build_scenario
        from evaluator import evaluate_single_plan

    改为:
        from core_imports import *
        # 或者
        from core_imports import build_scenario, evaluate_single_plan
"""

import sys
import os
import importlib
import importlib.util

# 添加当前目录到搜索路径
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 核心模块列表
_CORE_MODULES = [
    "scenario_builder",
    "evaluator",
    "llm_interface_cloud",
    "prompt_templates",
    "utils",
]


def _import_with_fallback(module_name):
    """
    尝试导入编译后的.pyd模块，如果不存在则导入.py源码
    """
    # 首先检查.pyd文件是否存在
    pyd_path = os.path.join(_HERE, f"{module_name}.pyd")
    py_path = os.path.join(_HERE, f"{module_name}.py")

    # 优先尝试导入.pyd文件
    if os.path.exists(pyd_path):
        try:
            spec = importlib.util.spec_from_file_location(
                module_name,
                pyd_path
            )
            if spec and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            print(f"[警告] 加载 {module_name}.pyd 失败: {e}")

    # 如果.pyd不存在或加载失败，尝试.py源文件
    if os.path.exists(py_path):
        try:
            spec = importlib.util.spec_from_file_location(
                module_name,
                py_path
            )
            if spec and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            print(f"[警告] 加载 {module_name}.py 失败: {e}")

    # 最后尝试标准导入
    try:
        module = importlib.import_module(module_name)
        return module
    except ImportError as e:
        print(f"[警告] 无法加载模块 {module_name}: {e}")
        return None


# 导入所有核心模块
for _mod_name in _CORE_MODULES:
    _mod = _import_with_fallback(_mod_name)
    if _mod:
        # 将模块中的所有公开对象导入到当前命名空间
        globals()[_mod_name] = _mod
        # 导出模块中的常用函数和类
        for _attr_name in getattr(_mod, '__all__', dir(_mod)):
            if not _attr_name.startswith('_'):
                globals()[_attr_name] = getattr(_mod, _attr_name)


def check_compilation_status():
    """
    检查模块编译状态
    返回: dict - 各模块的编译状态
    """
    status = {}
    for module_name in _CORE_MODULES:
        pyd_path = os.path.join(_HERE, f"{module_name}.pyd")
        py_path = os.path.join(_HERE, f"{module_name}.py")

        if os.path.exists(pyd_path):
            status[module_name] = "compiled"  # 已编译
        elif os.path.exists(py_path):
            status[module_name] = "source"    # 源码
        else:
            status[module_name] = "missing"   # 缺失

    return status


def print_compilation_status():
    """打印模块编译状态"""
    status = check_compilation_status()

    print("\n模块编译状态:")
    print("-" * 50)
    for module, state in status.items():
        if state == "compiled":
            print(f"  [OK] {module:30s} [已编译]")
        elif state == "source":
            print(f"  [..] {module:30s} [源码]")
        else:
            print(f"  [!!] {module:30s} [缺失]")
    print("-" * 50)
    print()


# 在模块加载时自动打印状态（可选，取消注释启用）
# print_compilation_status()
