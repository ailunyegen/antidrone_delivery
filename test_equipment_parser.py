"""assets / 装备解析自测（T4 验收用）。

用法:
    python test_equipment_parser.py

覆盖两类真实输入格式与若干边界情况，全部通过时退出码为 0：

1. **详细格式**（用户实际使用的格式）：`-名称(雷达，型号：YLC-12 …，位置：…)`，
   多条用 `|` 分隔，带 `探测设备：` / `反制设备：` 分组标题行；
2. **简洁格式**（手册 5.5 节）：`装备名 数量`，一行一件。

断言重点：不把分组标题当成装备、不被型号里的数字带偏、同一装备只出现一次、
`actionCount == len(actions)`、反制设备不会被探测设备挤掉。
"""
from __future__ import annotations

import json
import re
import sys

import equipment_parser as ep

DETAILED_SAMPLE = (
    "探测设备：\n"
    "-T1北部BC波段补盲雷达(雷达，型号：YLC-12 C波段低空补盲雷达，位置：116.5870°E 40.0846°N海拔65m,"
    "方位角180°俯仰角：0°,探测距离：5000m,方位覆盖300°,高度范围0-300m)"
    " |T1东部频谱侦测端(频谱侦测，型号 URD360全频段无人机侦测设备，位置116.5917°E 40.0810°N海拔45m,"
    "方位角：270°俯仰角 0°,探测距离：8000m,方位覆盖360°,高度范围：0-1000m)"
    " |T1南部可见光周视端(光电，型号 玄武号可见光周视搜索系统，位置116.5870°E 40.0774°N海拔52m)\n"
    "-T1西部BRID侦测终端(远程识别，型号 HY-R1D01 手持式RID侦测设备，数量：2台)\n"
    "-T1东南声学阵列(声学探测，型号 AS-208 208通道声学探测阵列，1套)\n"
    "反制设备：\n"
    "-T1定向干扰端A(定向干扰，型号 DJ-500，C2链路压制，2套)"
    " |T1导航诱骗站(型号 NS-300，GNSS诱骗，1套)"
    " |T1网捕站(型号 ZBW-HW03，手持网捕枪，2具)\n"
    "-某新型便携干扰器(XJ-9，背包式，2台)\n"
)

SIMPLE_SAMPLE = (
    "JY-17B低空搜索雷达 2部\n"
    "DWL-200车载电子对抗系统 1套\n"
    "天猎-1拦截无人机 6架\n"
    "红旗-17A近程防空导弹 2套\n"
    "CHL-802反无人机干扰枪 4支\n"
)

EXPECTED_DETAILED = {
    "T1-RADAR-N": "探测",
    "T1-SIGINT-E": "探测",
    "T1-EO-S": "探测",
    "T1-RID-W": "探测",
    "T1-ACOU-SE": "探测",
    "T1-JAM-A": "反制",
    "T1-SPOOF": "反制",
    "T1-NET": "反制",
    "XJ-9": "反制",
}
EXPECTED_SIMPLE = {"JY-17B": "探测", "DWL-200": "反制", "TL-1": "反制", "HQ-17A": "反制", "CHL-802": "反制"}

FAKE_PLAN = """1. 侦察预警阶段
使用T1北部BC波段补盲雷达与T1东部频谱侦测端建立空情态势。

2. 电子压制阶段
T1定向干扰端A对无人机C2链路实施压制，T1导航诱骗站实施导航诱骗。

3. 拦截打击阶段
T1网捕站实施网捕，必要时引导火力打击。

4. 效果评估阶段
评估毁伤效果并调整部署。
"""

FAILURES: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(label)
        print(f"  [FAIL] {label} {detail}")


def check_assets(assets_text: str, expected: dict, label: str) -> dict:
    library = ep.load_equipment_library()
    matched = ep.match_all_assets(assets_text, library)
    got = {entry["resourceId"]: entry["type"] for entry, _raw in matched}
    check(got == expected, f"{label}：装备识别完整且类型正确", f"got={got}")
    return {"library": library, "matched": matched, "got": got}


def main() -> int:
    print("== T4 装备解析自测 ==")
    library = ep.load_equipment_library()
    check(len(library) >= 20, "装备库已加载", f"len={len(library)}")

    print("\n-- 详细格式 --")
    context = check_assets(DETAILED_SAMPLE, EXPECTED_DETAILED, "详细格式")
    check(
        all(not rid.endswith(("：", ":")) for rid in context["got"]),
        "分组标题行未混进装备（探测设备：/反制设备：）",
    )
    check(ep.match_equipment("探测设备：", library) is None, "分组标题行直接被丢弃")
    check(
        ep.extract_equipment_name("-T1北部BC波段补盲雷达(雷达，型号：YLC-12") == "T1北部BC波段补盲雷达",
        "名称提取在括号处截断，不被型号/坐标干扰",
    )
    synthetic = next((e for e, _ in context["matched"] if e["resourceId"] == "XJ-9"), None)
    check(synthetic is not None and synthetic.get("matched") is False, "未知装备走合成路径并取型号作为 ID")
    check(synthetic is not None and synthetic["type"] == "反制", "未知装备按关键词推断为反制")

    plan = ep.build_structured_plan_json("任务", "态势", DETAILED_SAMPLE, FAKE_PLAN, library=library)
    ids = [a["resourceId"] for a in plan["actions"]]
    check(plan["actionCount"] == len(plan["actions"]), "actionCount == len(actions)")
    check(len(ids) == len(set(ids)), "同一装备不重复出现", f"ids={ids}")
    check(set(ids) == set(EXPECTED_DETAILED), "全部装备都进入 actions", f"ids={ids}")
    counter_ids = {rid for rid, etype in EXPECTED_DETAILED.items() if etype == "反制"}
    check(sum(1 for rid in ids if rid in counter_ids) == len(counter_ids),
          "反制装备全部保留，未被探测装备挤掉", f"ids={ids}")
    check(list(plan.keys()) == ["planId", "planName", "targetName", "generateTime", "actionCount", "actions"],
          "顶层键与 conversion_result.json 骨架一致")
    check(all(len(a) == 6 for a in plan["actions"]), "每个 action 固定 6 个字段")
    check(json.dumps(plan, ensure_ascii=False) is not None, "结果可 JSON 序列化")

    print("\n-- 简洁格式 --")
    check_assets(SIMPLE_SAMPLE, EXPECTED_SIMPLE, "简洁格式")
    simple_plan = ep.build_structured_plan_json("任务", "态势", SIMPLE_SAMPLE, FAKE_PLAN, library=library)
    check(simple_plan["actionCount"] == len(simple_plan["actions"]) == 5, "简洁格式 actionCount 正确")

    print("\n-- 边界情况 --")
    check(ep.match_all_assets("", library) == [], "空输入不产生装备")
    check(ep.match_all_assets("探测设备：\n反制设备：\n", library) == [], "只有分组标题时不产生装备")
    check(len(ep.match_all_assets("JY-17B低空搜索雷达 2部；DWL-200车载电子对抗系统 1套", library)) == 2,
          "分号分隔可识别")
    check(len(ep.match_all_assets("· 天猎-1拦截无人机 6架\n• 红旗-17A近程防空导弹 2套", library)) == 2,
          "项目符号可识别")
    quantity = ep.extract_quantity("红旗-17A近程防空导弹 2套")
    check(quantity == 2, "数量解析正确", f"qty={quantity}")
    check(ep.extract_quantity("T1东部频谱侦测端(型号 URD360，探测距离：8000m)") is None,
          "括号里的数字不会被误当成数量")

    print("\n== 结果 ==")
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
