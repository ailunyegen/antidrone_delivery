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

    # 导出
    st.divider()
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            "导出方案文本", data=plan,
            file_name=f"antidrone_plan_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )
    with col_dl2:
        import json as _json
        from datetime import datetime, timezone, timedelta
        tz = timezone(timedelta(hours=8))
        json_data = _json.dumps({
            "plan_id": f"web_plan_{time.strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now(tz).isoformat(timespec="seconds"),
            "model": client.model if client else "unknown",
            "provider": client.provider if client else "unknown",
            "focus": focus,
            "mission_objective": mission_objective,
            "situation_description": situation,
            "friendly_assets": assets,
            "hard_constraints": [l.strip() for l in hc_text.splitlines() if l.strip()],
            "soft_constraints": [
                {"description": p[0].strip(), "weight": float(p[1]) if len(p)>1 and p[1].strip() else None}
                for line in sc_text.splitlines() if line.strip()
                for p in [line.split(";", 1)]
            ],
            "plan_content": plan,
            "evaluation": eval_result if "error" not in eval_result else None,
        }, ensure_ascii=False, indent=2)
        st.download_button(
            "导出方案 JSON", data=json_data,
            file_name=f"antidrone_plan_{time.strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
