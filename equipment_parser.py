"""assets.txt 装备解析 + 方案文本 → 结构化行动 JSON 的共用实现（T4）。

背景：原实现把「一个输入行」当作「一件装备」，并用 `re.split(r'\\s+\\d+')` 猜名字。
遇到真实输入（`|` 分隔多条、名称后跟括号参数与型号数字）时只能识别出第一条，
于是输出方案里只剩一个探测设备。本模块改为：

1. **先切分条目**：按换行与 `|` / `；` 切分，并去掉 `-`、`·`、`•` 等项目符号；
2. **再按装备库匹配**：对「名称区」（首个括号/逗号之前）做**最长匹配**，名称区不中
   再退回整条文本匹配；这样名称里的型号数字、坐标、括号参数都不会干扰；
3. **最后才回退合成条目**：并从关键词推断「探测 / 反制」，而不是一律当探测设备；
   同时跳过 `探测设备：` 这类分组标题行。

四种使用方式（命令行交互 / Web / 脚本 / 研究管线中的前三种）共用本模块，
避免 main_compiled.py 与 web_app.py 各维护一份解析逻辑。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "load_equipment_library",
    "split_asset_entries",
    "extract_quantity",
    "extract_equipment_name",
    "match_equipment",
    "match_all_assets",
    "classify_action",
    "build_structured_plan_json",
]

_LIBRARY_CACHE: Optional[List[Dict[str, Any]]] = None

# 条目分隔符：换行、竖线（半/全角）、分号（半/全角）
_ENTRY_SEPARATOR = re.compile(r"[\n\r|｜;；]+")
# 行首项目符号
_MARKER_CHARS = "-–—*·•●○▪◦>》)、 "
# 名称区终止符（其后是参数/型号/数量说明）
_NAME_STOP_CHARS = "(（,，:：=＝[【"
# 数量：数量:3 / x3 / ×3 / 3部 / 3 套 / 3架 ...
_QUANTITY_PATTERNS = (
    re.compile(r"(?:数量|数目|共)\s*[:：]?\s*(\d+)"),
    re.compile(r"[x×*]\s*(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:部|套|台|架|辆|个|具|门|枚|发|组|座|支|把|艘|架次)"),
    re.compile(r"\b(\d+)\s*$"),
)
# 分组标题行（不是装备）
_HEADER_WORDS = (
    "探测设备", "侦察设备", "反制设备", "干扰设备", "拦截设备", "打击设备",
    "我方资源", "我方装备", "装备清单", "资源清单", "资产清单", "设备清单",
    "探测手段", "反制手段", "装备", "资源", "清单", "如下", "说明",
)
# 探测类关键词 / 反制类关键词（用于无法匹配装备库时的类型推断）
_DETECT_KEYWORDS = (
    "雷达", "探测", "侦测", "侦察", "光电", "红外", "频谱", "无线电侦测", "声学",
    "瞭望", "预警", "监视", "搜索", "周视", "补盲", "识别", "跟踪", "哨",
)
_COUNTER_KEYWORDS = (
    "干扰", "压制", "对抗", "欺骗", "诱骗", "劫持", "接管", "激光", "微波", "高功率",
    "导弹", "拦截", "网捕", "高炮", "近防", "密集阵", "弹幕", "打击", "毁伤", "火力",
    "无人机拦截", "捕网", "电子战", "电磁",
)
_MODEL_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+")
_ALNUM_OR_CJK = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]")


# ────────────────────────────── 装备库 ──────────────────────────────

def load_equipment_library(
    library_path: Optional[str | Path] = None,
    refresh: bool = False,
) -> List[Dict[str, Any]]:
    """加载 equipment_library.json（进程内缓存）。

    默认路径为与本模块同目录的 equipment_library.json；缺文件时返回空表，
    调用方会自动走「合成条目」的回退路径。
    """
    global _LIBRARY_CACHE
    if library_path is None and _LIBRARY_CACHE is not None and not refresh:
        return _LIBRARY_CACHE

    path = Path(library_path) if library_path else Path(__file__).resolve().parent / "equipment_library.json"
    library: List[Dict[str, Any]] = []
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                library = json.load(handle).get("equipment", []) or []
    except (OSError, ValueError):
        library = []

    if library_path is None:
        _LIBRARY_CACHE = library
    return library


# ────────────────────────────── 条目切分 ──────────────────────────────

def split_asset_entries(text: str) -> List[str]:
    """把 assets.txt 文本切成一条条装备条目。

    支持：一行一件、`|` 分隔多件同处一行、`；` 分隔、行首 `-`/`·`/`•` 等符号。
    """
    entries: List[str] = []
    for chunk in _ENTRY_SEPARATOR.split(text or ""):
        cleaned = chunk.strip().strip(_MARKER_CHARS).strip()
        cleaned = cleaned.lstrip(_MARKER_CHARS).strip()
        if cleaned:
            entries.append(cleaned)
    return entries


def _name_region(entry: str) -> str:
    """取「名称区」：第一个括号/逗号/冒号等参数分隔符之前的部分。"""
    head = entry
    for char in _NAME_STOP_CHARS:
        index = head.find(char)
        if index > 0:
            head = head[:index]
    return head.strip().strip(_MARKER_CHARS)


def extract_equipment_name(entry: str) -> str:
    """提取装备名称（名称区再剥掉数量与参数尾巴）。"""
    head = _name_region(entry)
    # 去掉行尾的数量描述（如 “2部”“x3”）
    head = _QUANTITY_PATTERNS[2].sub("", head).strip()
    head = re.sub(r"\s+", " ", head).strip(_MARKER_CHARS).strip()
    return head


def extract_quantity(entry: str) -> Optional[int]:
    """从条目里解析数量，解析不到返回 None。"""
    for pattern in _QUANTITY_PATTERNS:
        match = pattern.search(entry)
        if match:
            try:
                value = int(match.group(1))
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    return None


def _is_header_like(entry: str, name: str) -> bool:
    """判断是否为分组标题行（如「探测设备：」），这类行不应合成装备。"""
    stripped = entry.strip()
    if stripped.endswith(("：", ":")) and len(name) <= 12:
        return True
    if name in _HEADER_WORDS:
        return True
    if not _ALNUM_OR_CJK.search(name):
        return True
    return False


# ────────────────────────────── 匹配 ──────────────────────────────

def _match_by_library(text: str, library: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """在装备库中做最长匹配（名称与别名一起参与）。"""
    best: Optional[Dict[str, Any]] = None
    best_length = 0
    for entry in library:
        candidates = [entry.get("name", "")] + list(entry.get("aliases") or [])
        for candidate in candidates:
            token = (candidate or "").strip()
            if len(token) < 2:
                continue
            if token in text and len(token) > best_length:
                best, best_length = entry, len(token)
    return best


def _infer_type(text: str) -> str:
    counter_hits = sum(1 for keyword in _COUNTER_KEYWORDS if keyword in text)
    detect_hits = sum(1 for keyword in _DETECT_KEYWORDS if keyword in text)
    return "反制" if counter_hits > detect_hits else "探测"


def _synthetic_resource_id(name: str, entry_text: str = "") -> str:
    """给未匹配到的装备生成可读 ID：优先用型号串（名称区优先，其次整条文本），
    都没有再用名称压缩。"""
    for candidate in (name, entry_text):
        if not candidate:
            continue
        model = _MODEL_TOKEN.search(candidate)
        if model:
            return model.group(0)[:24]
    compact = re.sub(r"[\s()（）,，:：/\\]+", "-", name).strip("-")
    return (compact or "EQ")[:24]


def match_equipment(entry: str, library: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """把单条资产条目匹配为装备库条目；匹配不到时合成一个条目。

    返回的字典始终带 `resourceId` / `type` / `disposalCategory` /
    `disposalSubcategory` / `dispatchMode`，并附带 `matched` 与 `quantity` 便于排查。
    """
    library = library if library is not None else load_equipment_library()

    # 1) 名称区最长匹配（避免被括号里的型号串、坐标数字带偏）
    hit = _match_by_library(_name_region(entry), library)
    # 2) 名称区不中，再退回整条文本
    if hit is None:
        hit = _match_by_library(entry, library)
    if hit is not None:
        result = dict(hit)
        result["matched"] = True
        result["quantity"] = extract_quantity(entry)
        return result

    name = extract_equipment_name(entry)
    if not name or _is_header_like(entry, name):
        return None

    equipment_type = _infer_type(entry)
    category, subcategory, mode = classify_action(entry, None)
    return {
        "name": name[:60],
        "aliases": [],
        "resourceId": _synthetic_resource_id(name, entry),
        "type": equipment_type,
        "disposalCategory": category,
        "disposalSubcategory": subcategory,
        "dispatchMode": mode,
        "matched": False,
        "quantity": extract_quantity(entry),
    }


def match_all_assets(
    assets_text: str,
    library: Optional[List[Dict[str, Any]]] = None,
) -> List[Tuple[Dict[str, Any], str]]:
    """解析整份 assets 文本，返回 [(装备条目, 原始条目文本)]，按 resourceId 去重。"""
    library = library if library is not None else load_equipment_library()
    matched: List[Tuple[Dict[str, Any], str]] = []
    seen: set[str] = set()
    for entry_text in split_asset_entries(assets_text):
        entry = match_equipment(entry_text, library)
        if entry is None:
            continue
        resource_id = entry.get("resourceId") or ""
        if resource_id in seen:
            continue
        seen.add(resource_id)
        matched.append((entry, entry_text))
    return matched


# ────────────────────────────── 分类 ──────────────────────────────

def classify_action(text: str, equipment: Optional[Dict[str, Any]] = None) -> Tuple[int, int, int]:
    """返回 (处置大类, 处置小类, 下发模式)。装备库预配置优先，其次按文本关键词。"""
    if equipment and equipment.get("disposalCategory"):
        return (
            equipment["disposalCategory"],
            equipment.get("disposalSubcategory", 0),
            equipment.get("dispatchMode", 2),
        )

    if any(kw in text for kw in ["干扰", "压制", "电子对抗", "电磁", "对抗"]):
        if any(kw in text for kw in ["GNSS欺骗", "GPS欺骗", "导航欺骗"]):
            return (1, 102, 1)
        if any(kw in text for kw in ["GNSS压制", "GPS压制", "导航压制"]):
            return (1, 101, 1)
        if any(kw in text for kw in ["C2", "指挥链路", "数据链"]):
            return (1, 100, 2)
        if any(kw in text for kw in ["遥控", "射频"]):
            return (1, 103, 1)
        if any(kw in text for kw in ["雷达"]):
            return (1, 104, 2)
        return (1, 103, 2)
    if any(kw in text for kw in ["激光"]):
        return (2, 200, 2) if any(kw in text for kw in ["远距离", "远程"]) else (2, 201, 1)
    if any(kw in text for kw in ["微波", "HPM", "电磁脉冲"]):
        return (2, 202, 2)
    if any(kw in text for kw in ["网捕"]):
        return (3, 300, 3)
    if any(kw in text for kw in ["防空导弹", "导弹拦截", "HQ-", "红旗", "SAM", "导弹"]):
        return (4, 401, 2)
    if any(kw in text for kw in ["高射炮", "近防炮", "CIWS", "密集阵", "弹幕"]):
        return (4, 400, 1)
    if any(kw in text for kw in ["拦截无人机", "撞击", "物理撞击", "蜂群对抗", "拦截"]):
        return (4, 400, 2)
    if any(kw in text for kw in ["协议劫持", "链路接管", "劫持", "接管"]):
        return (5, 500, 3)
    if any(kw in text for kw in ["雷达", "探测", "侦察", "搜索", "预警", "侦测", "光电", "频谱"]):
        return (1, 104, 1)
    return (1, 103, 2)


# ────────────────────────────── 方案 JSON ──────────────────────────────

def _section_equipment_hits(
    section: str,
    matched: List[Tuple[Dict[str, Any], str]],
) -> List[Dict[str, Any]]:
    """找出方案章节文本中提到的装备（名称 / 别名 / 名称前 4 字）。"""
    hits: List[Dict[str, Any]] = []
    for entry, _raw in matched:
        name = entry.get("name", "")
        if name and name in section:
            hits.append(entry)
            continue
        if any(alias in section for alias in entry.get("aliases") or []):
            hits.append(entry)
            continue
        # 名称较长时，允许用前若干字命中（LLM 常写简称）
        if len(name) >= 6 and name[:4] in section:
            hits.append(entry)
    return hits


def _action_of(section: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    category, subcategory, mode = classify_action(section, entry)
    return {
        "dispatchMode": mode,
        "disposalCategory": category,
        "disposalSubcategory": subcategory,
        "estimatedDuration": 30,
        "resourceId": entry["resourceId"],
        "startTime": 0,
    }


def build_structured_plan_json(
    mission_objective: str,
    situation_description: str,
    friendly_assets: str,
    plan_content: str,
    plan_name: str = "反无人机行动方案",
    library: Optional[List[Dict[str, Any]]] = None,
    max_actions: int = 10,
) -> Dict[str, Any]:
    """按 conversion_result.json 骨架构建结构化方案 JSON。

    顶层键固定为 planId / planName / targetName / generateTime / actionCount / actions，
    每个 action 固定 6 个字段，且保证 actionCount == len(actions)。
    """
    del mission_objective, situation_description  # 当前骨架未使用，保留签名兼容

    library = library if library is not None else load_equipment_library()
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    now_ts = int(now.timestamp() * 1000)

    matched = match_all_assets(friendly_assets, library)

    actions: List[Dict[str, Any]] = []
    used: set[str] = set()

    def _append(section: str, entry: Dict[str, Any]) -> None:
        """追加一个行动；同一装备（resourceId）只出现一次。"""
        resource_id = entry.get("resourceId") or ""
        if not resource_id or resource_id in used:
            return
        used.add(resource_id)
        actions.append(_action_of(section, entry))

    for section in re.split(r"\n(?=\d+\.\s)", plan_content or ""):
        section = section.strip()
        if not section:
            continue
        found = _section_equipment_hits(section, matched)
        counters = [e for e in found if e.get("type") == "反制"]
        detectors = [e for e in found if e.get("type") != "反制"]
        for entry in (counters + detectors)[:2]:  # 每章节最多认领 2 件装备，反制优先
            if len(actions) >= max_actions:
                break
            _append(section, entry)

    # 方案文本里没提到的装备补齐：先反制、后探测
    for wanted_type in ("反制", "探测"):
        for entry, _raw in matched:
            if len(actions) >= max_actions:
                break
            is_counter = (entry.get("type") or "探测") == "反制"
            if is_counter != (wanted_type == "反制"):
                continue
            _append("", entry)

    final_actions = actions[:max_actions]
    for index, action in enumerate(final_actions):
        action["startTime"] = now_ts + index * 60000

    return {
        "planId": f"plan_{now.strftime('%Y%m%d%H%M%S')}",
        "planName": plan_name,
        "targetName": "UAV无人机群",
        "generateTime": now_ts,
        "actionCount": len(final_actions),
        "actions": final_actions,
    }
