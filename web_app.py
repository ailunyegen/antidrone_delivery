"""
反无人机行动方案智能生成系统 - Web 界面
启动方式: streamlit run web_app.py
或: python main.py --web
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from llm_interface_cloud import CloudLLMClient, list_providers, get_provider_config
    from prompt_templates import get_kill_chain_generation_prompt, build_constraints_from_app_inputs
    from evaluator import set_generate_text_func, evaluate_single_plan
    from utils import get_current_timestamp
except ImportError as e:
    st.error(f"无法导入必需模块: {e}")
    st.stop()

# -- 页面配置 --
st.set_page_config(page_title="反无人机行动方案生成系统", layout="wide")
st.title("反无人机行动方案智能生成系统")
st.caption(f"云端API版 | [{get_current_timestamp()}]")

# ============================================================
#  侧边栏: LLM 配置
# ============================================================

st.sidebar.header("LLM 配置")

providers = list_providers()
provider_id = st.sidebar.selectbox(
    "服务商", options=list(providers.keys()),
    format_func=lambda k: providers[k], index=0,
)
preset = get_provider_config(provider_id)

api_key = st.sidebar.text_input("API Key", type="password", placeholder=f"输入 {preset['name']} 的 API Key")

base_url = ""
if provider_id == "custom":
    base_url = st.sidebar.text_input("Base URL", placeholder="https://api.example.com/v1")

model = st.sidebar.text_input("模型名称", value=preset["default_model"])

with st.sidebar.expander("高级参数"):
    temperature = st.slider("生成温度", 0.0, 1.5, 0.7, 0.05)
    max_tokens = st.slider("最大输出 Token", 1000, 16000, 8000, 500)

def _get_client() -> CloudLLMClient | None:
    key = api_key
    if not key:
        import os
        key = os.getenv(preset["env_key"], "")
    if not key:
        return None
    try:
        return CloudLLMClient(
            provider=provider_id, api_key=key, model=model,
            base_url=base_url, temperature=temperature, max_tokens=max_tokens,
        )
    except Exception:
        return None

client = _get_client()
if client:
    st.sidebar.success(f"已连接: {client.model}")
    # 注入 LLM 函数到 evaluator
    set_generate_text_func(client.generate_json)
else:
    st.sidebar.warning("请填写 API Key")

# ============================================================
#  主界面
# ============================================================

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. 作战任务与想定")
    mission_objective = st.text_input("作战任务目标:", value="对敌方无人机集群实施探测、干扰与拦截，确保指挥所安全")

    situation_default = (
        "敌情: 敌方计划使用20架小型侦察无人机和12架FPV自杀式无人机对我方阵地实施集群突击。\n"
        "天气: 晴朗，能见度良好。\n"
        "地形: 开阔平原，我方阵地周围有少量建筑物。"
    )
    situation = st.text_area("战场态势:", height=150, value=situation_default)

    assets_default = (
        "JY-17B低空搜索雷达 2部\nDWL-200车载电子对抗系统 1套\n"
        "天猎-1拦截无人机 6架\n红旗-17A近程防空导弹 2套\nCHL-802反无人机干扰枪 4支"
    )
    assets = st.text_area("我方反无人机资源:", height=120, value=assets_default)

with col2:
    st.subheader("2. 作战约束")
    hc_text = st.text_area("硬性约束 (每条一行):", height=80,
                           value="必须在敌方无人机到达指挥所之前完成拦截\n禁止在未确认目标性质前开火")
    sc_text = st.text_area("柔性约束 (描述; 权重):", height=80,
                           value="优先使用软杀伤手段; 0.85\n实施分层拦截; 0.75")

    st.subheader("3. 方案侧重点")
    focus = st.selectbox("选择侧重点", [
        "探测效率和快速响应", "软硬杀伤协同和弹药节约", "创新的非对称反无人机战法"
    ])

# ============================================================
#  生成与评估
# ============================================================

st.divider()

if st.button("生成反无人机方案", type="primary", use_container_width=True, disabled=(client is None)):
    if not client:
        st.error("请先在侧边栏配置 API Key")
        st.stop()

    hard_constraints, soft_constraints = build_constraints_from_app_inputs(
        hard_constraints_text=hc_text, soft_constraints_text=sc_text,
    )

    prompt = get_kill_chain_generation_prompt(
        mission_objective=mission_objective,
        situation_description=situation,
        friendly_assets=assets,
        hard_constraints=hard_constraints,
        soft_constraints=soft_constraints,
        focus=focus,
    )

    # 生成
    st.subheader("生成的反无人机方案")
    plan = ""
    placeholder = st.empty()
    start = time.time()
    for chunk in client.generate_stream(prompt=prompt, max_tokens=max_tokens):
        plan += chunk
        placeholder.markdown(plan)
    elapsed = time.time() - start
    st.caption(f"生成完毕，耗时 {elapsed:.1f} 秒，共 {len(plan)} 字符")

    # 评估
    st.subheader("方案评估")
    with st.spinner("正在评估..."):
        eval_result = evaluate_single_plan(plan, hard_constraints, soft_constraints)

    if "error" in eval_result:
        st.warning(f"评估出错: {eval_result['error']}")
    else:
        st.markdown(f"**总结:** {eval_result.get('plan_summary', '无')}")

        for hc in eval_result.get("hard_constraint_checks", []):
            status = "通过" if hc.get("pass") else "未通过"
            st.markdown(f"- 硬约束 `{hc['constraint_id']}`: **{status}**")
            st.caption(f"  {hc.get('reasoning', '')}")

        for sc in eval_result.get("soft_constraint_scores", []):
            st.markdown(f"- 软约束 `{sc['constraint_id']}`: **{sc.get('score', 0)}/10**")
            st.caption(f"  {sc.get('reasoning', '')}")

    # 导出（仅 JSON，按 conversion_result.json 骨架）
    st.divider()
    import json as _json
    from datetime import datetime, timezone, timedelta

    # 构建设备清单文本
    assets_text = assets

    # 在 web_app.py 中内联 build_structured_plan_json（避免循环导入）
    def _build_structured_plan_json_web(
        mission_obj: str, situation: str, assets_txt: str,
        plan_text: str, plan_name: str,
    ) -> dict:
        import re as _re
        from datetime import datetime, timezone, timedelta
        from pathlib import Path as _Path
        tz = timezone(timedelta(hours=8))
        now_ts = int(datetime.now(tz).timestamp() * 1000)
        NL = chr(10)

        # Load equipment library (cached via st.session_state)
        if "_eq_library" not in st.session_state:
            _lib_path = _Path(__file__).resolve().parent / "equipment_library.json"
            if _lib_path.exists():
                import json as _json
                st.session_state["_eq_library"] = _json.loads(_lib_path.read_text(encoding="utf-8")).get("equipment", [])
            else:
                st.session_state["_eq_library"] = []
        library = st.session_state["_eq_library"]

        def _match_eq(line):
            ln = line.strip().lstrip('-').strip()
            if '(' in ln: ln = ln.split('(')[0].strip()
            ln = _re.split(r'\s+\d+', ln)[0].strip()
            for e in library:
                if e["name"] in ln or ln in e["name"]: return e
            for e in library:
                for a in e.get("aliases", []):
                    if a in line or a in ln: return e
            return {"name": ln[:20], "aliases": [], "resourceId": ln.replace(" ","-")[:12],
                     "type": "探测", "disposalCategory": 1, "disposalSubcategory": 104, "dispatchMode": 1}

        def _classify(text, eq=None):
            if eq and eq.get("disposalCategory"):
                return (eq["disposalCategory"], eq["disposalSubcategory"], eq.get("dispatchMode",2))
            if any(k in text for k in ["干扰","压制","电子对抗","电磁"]):
                if any(k in text for k in ["GNSS欺骗","GPS欺骗","导航欺骗"]): return (1,102,1)
                if any(k in text for k in ["GNSS压制","GPS压制","导航压制"]): return (1,101,1)
                if any(k in text for k in ["C2","指挥链路","数据链"]): return (1,100,2)
                if any(k in text for k in ["遥控","射频"]): return (1,103,1)
                if any(k in text for k in ["雷达"]): return (1,104,2)
                return (1,103,2)
            if any(k in text for k in ["激光"]): return (2,200,2) if any(k in text for k in ["远距离","远程"]) else (2,201,1)
            if any(k in text for k in ["微波","HPM","电磁脉冲"]): return (2,202,2)
            if any(k in text for k in ["网捕"]): return (3,300,3)
            if any(k in text for k in ["防空导弹","导弹拦截","HQ-","红旗","SAM"]): return (4,401,2)
            if any(k in text for k in ["高射炮","近防炮","CIWS","密集阵","弹幕"]): return (4,400,1)
            if any(k in text for k in ["拦截无人机","撞击","物理撞击","蜂群对抗"]): return (4,400,2)
            if any(k in text for k in ["协议劫持","链路接管"]): return (5,500,3)
            if any(k in text for k in ["雷达","探测","侦察","搜索","预警"]): return (1,104,1)
            return (1,103,2)

        asset_lines = [l.strip() for l in assets_txt.splitlines() if l.strip()]
        matched = []
        seen = set()
        for l in asset_lines:
            m = _match_eq(l)
            if m and m["resourceId"] not in seen:
                matched.append((m, l))
                seen.add(m["resourceId"])

        actions = []
        sections = _re.split(NL + r'(?=\d+\.\s)', plan_text)
        for section in sections:
            if not section.strip(): continue
            found = []
            for entry, _ in matched:
                if entry["name"] in section: found.append(entry); continue
                for alias in entry.get("aliases", []):
                    if alias in section and len(alias) > 2: found.append(entry); break
            detectors = [e for e in found if e.get("type")=="探测"]
            counters = [e for e in found if e.get("type")=="反制"]
            for entry in (counters + detectors)[:2]:
                c, s, m = _classify(section, entry)
                actions.append({"dispatchMode":m,"disposalCategory":c,"disposalSubcategory":s,"estimatedDuration":30,"resourceId":entry["resourceId"],"startTime":0})

        existing = {a["resourceId"] for a in actions}
        for entry, _ in matched:
            if entry["resourceId"] not in existing and entry.get("type")=="反制":
                c,s,m = _classify("", entry)
                actions.append({"dispatchMode":m,"disposalCategory":c,"disposalSubcategory":s,"estimatedDuration":30,"resourceId":entry["resourceId"],"startTime":0})
                existing.add(entry["resourceId"])
        for entry, _ in matched:
            if entry["resourceId"] not in existing:
                c,s,m = _classify("", entry)
                actions.append({"dispatchMode":m,"disposalCategory":c,"disposalSubcategory":s,"estimatedDuration":30,"resourceId":entry["resourceId"],"startTime":0})
                existing.add(entry["resourceId"])

        for i, a in enumerate(actions): a["startTime"] = now_ts + i * 60000
        final = actions[:10]
        return {"planId": f"plan_{datetime.now(tz).strftime('%Y%m%d%H%M%S')}",
                "planName": plan_name,
                "targetName": "UAV无人机群",
                "generateTime": now_ts,
                "actionCount": len(final),
                "actions": final}

    json_data = _json.dumps(
        _build_structured_plan_json_web(
            mission_objective, situation, assets_text, plan,
            f"反无人机行动方案 (侧重点: {focus})",
        ),
        ensure_ascii=False, indent=2,
    )
    st.download_button(
        "导出方案 JSON", data=json_data,
        file_name=f"antidrone_plan_{time.strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )
