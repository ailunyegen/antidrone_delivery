"""
反无人机行动方案智能生成系统 (编译版入口)
使用编译后的动态链接库模块

使用方法:
    python main_compiled.py                  # 交互式命令行
    python main_compiled.py --web            # 启动 Web 界面
"""
from __future__ import annotations

def build_constraints_from_app_inputs(hard_constraints_text: str = "", soft_constraints_text: str = ""):
    """从交互式输入构建约束结构。

    hard_constraints_text: 多行硬约束文本，每行为一条约束。
    soft_constraints_text: 多行软约束文本，每行为 "描述; 权重" 或仅描述。
    返回 (hard_constraints_list, soft_constraints_list)
    soft_constraints_list 中项为 (描述, 权重(float)) 或 (描述, None) 当权重无法解析时。
    """
    hard = [line.strip() for line in hard_constraints_text.splitlines() if line.strip()]

    soft = []
    for line in soft_constraints_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" in line:
            parts = [p.strip() for p in line.split(";", 1)]
            desc = parts[0]
            weight = None
            try:
                weight = float(parts[1])
            except Exception:
                # 尝试替换中文逗号/空格
                try:
                    weight = float(parts[1].replace("，", ","))
                except Exception:
                    weight = None
            soft.append((desc, weight))
        else:
            soft.append((line, None))

    return hard, soft

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 将当前目录加入搜索路径
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# 使用兼容性导入层（自动选择编译版或源码版）
from core_imports import *

# 兼容性处理: 如果 core_imports 未提供 CloudLLMClient，则定义一个占位类以便给出友好错误提示
if "CloudLLMClient" not in globals():
    class CloudLLMClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "CloudLLMClient 未找到。请确认 core_imports 模块存在并导出 CloudLLMClient 类，或使用源码版库。"
            )

def load_config(config_path: str = "config.json") -> dict:
    """加载配置文件。"""
    path = Path(config_path)
    if not path.exists():
        print(f"[错误] 配置文件不存在: {path}")
        print("请复制 config.example.json 为 config.json 并填写 api_key。")
        sys.exit(1)
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 环境变量覆盖
    if not cfg.get("api_key"):
        for env_key in [
            "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY",
            "ZHIPUAI_API_KEY", "MOONSHOT_API_KEY", "SILICONFLOW_API_KEY",
            "ANTIDRONE_API_KEY",
        ]:
            val = os.getenv(env_key, "")
            if val:
                cfg["api_key"] = val
                break
    if not cfg.get("api_key"):
        print("[错误] 未配置 api_key。请在 config.json 中填写，或设置环境变量。")
        sys.exit(1)
    return cfg

def init_client(cfg: dict):
    """初始化云端 LLM 客户端。"""
    # 使用导入的CloudLLMClient类
    return CloudLLMClient(
        provider=cfg.get("provider", "deepseek"),
        api_key=cfg["api_key"],
        model=cfg.get("model", ""),
        base_url=cfg.get("base_url", ""),
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens", 8000),
    )

def get_kill_chain_generation_prompt(
    mission_objective: str,
    situation_description: str,
    friendly_assets: str,
    hard_constraints,
    soft_constraints,
    focus: str,
) -> str:
    """生成反无人机行动方案的文本提示。"""
    def _format_constraints(constraints):
        if isinstance(constraints, str):
            return constraints.strip() or "无"
        if not constraints:
            return "无"
        if all(isinstance(item, tuple) and len(item) == 2 for item in constraints):
            return "\n".join(f"- {desc} (权重 {weight})" for desc, weight in constraints)
        return "\n".join(f"- {item}" for item in constraints)

    hard_text = _format_constraints(hard_constraints)
    soft_text = _format_constraints(soft_constraints)

    return (
        "你是一名反无人机战法专家。请基于以下任务目标、态势、我方资源、硬性约束与柔性约束，\n"
        "生成一个完整的反无人机行动方案，包含情报获取、侦察预警、电子对抗、拦截与后续评估等环节。\n\n"
        f"任务目标:\n{mission_objective.strip()}\n\n"
        f"战场态势:\n{situation_description.strip()}\n\n"
        f"我方资源:\n{friendly_assets.strip()}\n\n"
        "硬性约束:\n"
        f"{hard_text}\n\n"
        "柔性约束:\n"
        f"{soft_text}\n\n"
        f"侧重点: {focus}\n\n"
        "请按以下结构输出:\n"
        "1. 作战总体思路\n"
        "2. 目标识别与优先级\n"
        "3. 侦察与预警方案\n"
        "4. 电子干扰与拦截方案\n"
        "5. 后勤保障与人员安全\n"
        "6. 风险评估与应对措施\n"
    )

_equipment_library_cache = None

def _load_equipment_library():
    """从 equipment_library.json 加载装备库（带内存缓存）。"""
    global _equipment_library_cache
    if _equipment_library_cache is not None:
        return _equipment_library_cache
    import json as _json
    _lib_path = Path(__file__).resolve().parent / "equipment_library.json"
    if not _lib_path.exists():
        _equipment_library_cache = []
        return []
    with _lib_path.open("r", encoding="utf-8") as _f:
        _equipment_library_cache = _json.load(_f).get("equipment", [])
    return _equipment_library_cache


def _match_equipment(asset_line: str, library: list) -> dict | None:
    """在装备库中匹配资产行，返回装备条目或 None。
    支持两种格式: '装备名 数量' 和 '-位置 装备名(参数...)'
    """
    line = asset_line.strip().lstrip('-').strip()
    
    # 提取纯装备名: 取 '(' 前的内容，去除型号/坐标等参数
    if '(' in line:
        name_part = line.split('(')[0].strip()
    else:
        name_part = line.strip()
    
    # 去掉可能的数量后缀
    import re as _re
    name_part = _re.split(r'\s+\d+', name_part)[0].strip()
    
    # 在库中匹配: 先精确匹配 name，再匹配 aliases
    for entry in library:
        if entry["name"] in name_part or name_part in entry["name"]:
            return entry
    for entry in library:
        for alias in entry.get("aliases", []):
            if alias in asset_line or alias in name_part:
                return entry
    
    # 回退: 提取可读短名作为 ID
    short_name = name_part[:20].strip()
    if short_name:
        return {
            "name": short_name,
            "aliases": [],
            "resourceId": short_name.replace(" ", "-")[:12],
            "type": "探测",
            "disposalCategory": 1,
            "disposalSubcategory": 104,
            "dispatchMode": 1,
        }
    return None


def _classify_action(text: str, equipment: dict | None = None) -> tuple:
    """根据装备库配置分类。优先使用装备预配置值，回退到文本关键词。"""
    if equipment and equipment.get("disposalCategory"):
        return (
            equipment["disposalCategory"],
            equipment["disposalSubcategory"],
            equipment.get("dispatchMode", 2),
        )
    
    # 文本关键词回退
    if any(kw in text for kw in ["干扰", "压制", "电子对抗", "电磁"]):
        if any(kw in text for kw in ["GNSS欺骗", "GPS欺骗", "导航欺骗"]): return (1, 102, 1)
        if any(kw in text for kw in ["GNSS压制", "GPS压制", "导航压制"]): return (1, 101, 1)
        if any(kw in text for kw in ["C2", "指挥链路", "数据链"]): return (1, 100, 2)
        if any(kw in text for kw in ["遥控", "射频"]): return (1, 103, 1)
        if any(kw in text for kw in ["雷达"]): return (1, 104, 2)
        return (1, 103, 2)
    if any(kw in text for kw in ["激光"]):
        return (2, 200, 2) if any(kw in text for kw in ["远距离", "远程"]) else (2, 201, 1)
    if any(kw in text for kw in ["微波", "HPM", "电磁脉冲"]): return (2, 202, 2)
    if any(kw in text for kw in ["网捕"]): return (3, 300, 3)
    if any(kw in text for kw in ["防空导弹", "导弹拦截", "HQ-", "红旗", "SAM"]): return (4, 401, 2)
    if any(kw in text for kw in ["高射炮", "近防炮", "CIWS", "密集阵", "弹幕"]): return (4, 400, 1)
    if any(kw in text for kw in ["拦截无人机", "撞击", "物理撞击", "蜂群对抗"]): return (4, 400, 2)
    if any(kw in text for kw in ["协议劫持", "链路接管"]): return (5, 500, 3)
    if any(kw in text for kw in ["雷达", "探测", "侦察", "搜索", "预警"]): return (1, 104, 1)
    return (1, 103, 2)


def build_structured_plan_json(
    mission_objective: str,
    situation_description: str,
    friendly_assets: str,
    plan_content: str,
    plan_name: str = "反无人机行动方案",
) -> dict:
    """按照 conversion_result.json 骨架构建结构化方案 JSON。
    从 equipment_library.json 加载装备库，支持 assets.txt 新旧两种格式。
    """
    import re as _re
    from datetime import datetime, timezone, timedelta

    library = _load_equipment_library()
    NL = chr(10)
    tz = timezone(timedelta(hours=8))
    now_ts = int(datetime.now(tz).timestamp() * 1000)

    # ── 解析 assets.txt，匹配装备库（按 resourceId 去重）──
    asset_lines = [l.strip() for l in friendly_assets.splitlines() if l.strip()]
    matched_equipment = []
    seen_rids = set()
    for line in asset_lines:
        entry = _match_equipment(line, library)
        if entry and entry["resourceId"] not in seen_rids:
            matched_equipment.append((entry, line))
            seen_rids.add(entry["resourceId"])

    # ── 从 LLM 方案文本中提取行动 ──
    actions = []
    sections = _re.split(NL + r'(?=\d+\.\s)', plan_content)
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
        
        found_in_section = []
        for entry, line in matched_equipment:
            # 检查装备名或别名是否出现在此章节
            eq_name = entry["name"]
            if eq_name in section:
                found_in_section.append(entry)
                continue
            for alias in entry.get("aliases", []):
                if alias in section and len(alias) > 2:
                    found_in_section.append(entry)
                    break
        
        # 每个章节最多收录 2 个行动，优先反制设备
        detectors = [e for e in found_in_section if e.get("type") == "探测"]
        counters = [e for e in found_in_section if e.get("type") == "反制"]
        selected = (counters + detectors)[:2]
        
        for entry in selected:
            cat, subcat, mode = _classify_action(section, entry)
            actions.append({
                "dispatchMode": mode,
                "disposalCategory": cat,
                "disposalSubcategory": subcat,
                "estimatedDuration": 30,
                "resourceId": entry["resourceId"],
                "startTime": 0,
            })

    # ── Fallback: 方案文本中未出现的装备，按类型补充 ──
    existing_rids = {a["resourceId"] for a in actions}
    # 优先补充反制设备，避免重复
    for entry, _ in matched_equipment:
        if entry["resourceId"] not in existing_rids and entry.get("type") == "反制":
            cat, subcat, mode = _classify_action("", entry)
            actions.append({
                "dispatchMode": mode,
                "disposalCategory": cat,
                "disposalSubcategory": subcat,
                "estimatedDuration": 30,
                "resourceId": entry["resourceId"],
                "startTime": 0,
            })
            existing_rids.add(entry["resourceId"])
    # 再补充探测设备
    for entry, _ in matched_equipment:
        if entry["resourceId"] not in existing_rids:
            cat, subcat, mode = _classify_action("", entry)
            actions.append({
                "dispatchMode": mode,
                "disposalCategory": cat,
                "disposalSubcategory": subcat,
                "estimatedDuration": 30,
                "resourceId": entry["resourceId"],
                "startTime": 0,
            })
            existing_rids.add(entry["resourceId"])

    # ── 填充 startTime ──
    for i, action in enumerate(actions):
        action["startTime"] = now_ts + i * 60000

    final_actions = actions[:10]
    return {
        "planId": f"plan_{datetime.now(tz).strftime('%Y%m%d%H%M%S')}",
        "planName": plan_name,
        "targetName": "UAV无人机群",
        "generateTime": now_ts,
        "actionCount": len(final_actions),
        "actions": final_actions,
    }


def run_interactive(client):
    """交互式命令行模式。"""
    print("=" * 60)
    print("  反无人机行动方案智能生成系统 (编译版)")
    print("=" * 60)
    print(f"  模型: {client.model}")
    print(f"  服务商: {client.provider}")
    print("=" * 60)

    # 显示模块编译状态
    print_compilation_status()

    # 收集输入
    print("\n[1] 请输入作战任务目标:")
    mission_objective = input(">>> ").strip()
    if not mission_objective:
        mission_objective = "对敌方无人机集群实施探测、干扰与拦截，确保指挥所安全"
        print(f"  (使用默认: {mission_objective})")

    print("\n[2] 请输入战场态势与敌情描述 (输入空行结束):")
    situation_lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        situation_lines.append(line)
    situation_description = "\n".join(situation_lines)
    if not situation_description:
        situation_description = (
            "敌情: 敌方计划使用20架小型侦察无人机和12架FPV自杀式无人机对我方阵地实施集群突击。\n"
            "天气: 晴朗，能见度良好。\n"
            "地形: 开阔平原，我方阵地周围有少量建筑物。"
        )
        print(f"  (使用默认态势)")

    print("\n[3] 请输入我方反无人机资源 (输入空行结束):")
    assets_lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        assets_lines.append(line)
    friendly_assets = "\n".join(assets_lines)
    if not friendly_assets:
        friendly_assets = (
            "JY-17B低空搜索雷达 2部\n"
            "DWL-200车载电子对抗系统 1套\n"
            "天猎-1拦截无人机 6架\n"
            "红旗-17A近程防空导弹 2套\n"
            "CHL-802反无人机干扰枪 4支"
        )
        print(f"  (使用默认资源)")

    print("\n[4] 硬性约束 (每条一行，输入空行结束):")
    hc_lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        hc_lines.append(line)
    if not hc_lines:
        hc_lines = [
            "必须在敌方无人机到达指挥所之前完成拦截",
            "禁止在未确认目标性质前开火",
            "拦截过程中必须保持至少一部雷达持续工作",
        ]
        print(f"  (使用默认硬约束)")

    print("\n[5] 柔性约束 (格式: 描述; 权重，每条一行，输入空行结束):")
    sc_lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        sc_lines.append(line)
    if not sc_lines:
        sc_lines = [
            "优先使用软杀伤手段; 0.85",
            "实施分层拦截; 0.75",
            "保留部分拦截无人机作为预备队; 0.65",
        ]
        print(f"  (使用默认软约束)")

    # 构建约束
    hard_constraints, soft_constraints = build_constraints_from_app_inputs(
        hard_constraints_text="\n".join(hc_lines),
        soft_constraints_text="\n".join(sc_lines),
    )

    # 生成方案
    focuses = ["探测效率和快速响应", "软硬杀伤协同和弹药节约", "创新的非对称反无人机战法"]

    for i, focus in enumerate(focuses):
        print(f"\n{'='*60}")
        print(f"  正在生成方案 {i+1}/3 (侧重点: {focus})...")
        print(f"{'='*60}\n")

        prompt = get_kill_chain_generation_prompt(
            mission_objective=mission_objective,
            situation_description=situation_description,
            friendly_assets=friendly_assets,
            hard_constraints=hard_constraints,
            soft_constraints=soft_constraints,
            focus=focus,
        )

        plan = ""
        start = time.time()
        for chunk in client.generate_stream(prompt=prompt, max_tokens=8000):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            plan += chunk
        elapsed = time.time() - start

        print(f"\n\n  [方案{i+1}生成完毕，耗时 {elapsed:.1f} 秒，共 {len(plan)} 字符]")

        # 保存方案（文本 + JSON）
        output_dir = _HERE / "output"
        output_dir.mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        plan_id = f"plan_{i+1}_{ts}"

        # 文本格式
        plan_file = output_dir / f"{plan_id}.txt"
        with plan_file.open("w", encoding="utf-8") as f:
            f.write(f"# 方案 {i+1} (侧重点: {focus})\n")
            f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 模型: {client.model}\n\n")
            f.write(plan)
        print(f"  已保存至: {plan_file}")

        # JSON 格式
        json_file = output_dir / f"{plan_id}.json"
        plan_json = build_structured_plan_json(
            mission_objective=mission_objective,
            situation_description=situation_description,
            friendly_assets=friendly_assets,
            hard_constraints=hard_constraints,
            soft_constraints=soft_constraints,
            focus=focus,
            plan_content=plan,
            client=client,
            plan_id=plan_id,
        )
        with json_file.open("w", encoding="utf-8") as f:
            json.dump(plan_json, f, ensure_ascii=False, indent=2)
        print(f"  已保存至: {json_file}")

    print(f"\n{'='*60}")
    print("  全部方案生成完毕!")
    print(f"{'='*60}")

def run_single(client, mission: str, situation: str, assets: str, output: str = ""):
    """单次生成模式 (用于脚本调用)。"""
    prompt = get_kill_chain_generation_prompt(
        mission_objective=mission,
        situation_description=situation,
        friendly_assets=assets,
        hard_constraints=[],
        soft_constraints=[],
        focus="综合效能最优化",
    )

    print("正在生成方案...\n")
    result = ""
    for chunk in client.generate_stream(prompt=prompt):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        result += chunk

    if output:
        # 文本格式
        # Text output removed — JSON only
        # 同路径 JSON 格式
        json_output = str(Path(output).with_suffix(".json"))
        plan_json = build_structured_plan_json(
            mission_objective=mission,
            situation_description=situation,
            friendly_assets=assets,
            plan_content=result,
            plan_name=mission[:20] + "反无人机方案",
        )
        Path(json_output).write_text(
            json.dumps(plan_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{chr(10)}{chr(10)}已保存至: {json_output}")
    return result

def main():
    parser = argparse.ArgumentParser(
        description="反无人机行动方案智能生成系统 (编译版)"
    )
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--web", action="store_true", help="启动 Web 界面")
    parser.add_argument("--mission", default="", help="作战任务目标 (单次模式)")
    parser.add_argument("--situation", default="", help="战场态势描述文件 (单次模式)")
    parser.add_argument("--assets", default="", help="我方资源描述文件 (单次模式)")
    parser.add_argument("--output", default="", help="输出文件路径 (单次模式)")
    parser.add_argument("--check", action="store_true", help="检查模块编译状态")
    args = parser.parse_args()

    # 检查编译状态
    if args.check:
        print_compilation_status()
        return

    cfg = load_config(args.config)
    client = init_client(cfg)

    if args.web:
        # 启动 Streamlit
        web_app = _HERE / "web_app.py"
        if not web_app.exists():
            print("[错误] web_app.py 不存在，无法启动 Web 界面。")
            sys.exit(1)
        os.system(f'streamlit run "{web_app}"')
    elif args.mission:
        # 单次生成模式
        situation = ""
        if args.situation:
            sit_path = Path(args.situation)
            if not sit_path.exists():
                print(f"[错误] 态势描述文件不存在: {sit_path}")
                sys.exit(1)
            situation = sit_path.read_text(encoding="utf-8")

        assets = ""
        if args.assets:
            ast_path = Path(args.assets)
            if not ast_path.exists():
                print(f"[错误] 资源描述文件不存在: {ast_path}")
                sys.exit(1)
            assets = ast_path.read_text(encoding="utf-8")

        run_single(client, args.mission, situation, assets, args.output)
    else:
        # 交互式模式
        run_interactive(client)

if __name__ == "__main__":
    main()
