# 反无人机行动方案智能生成系统

基于云端大模型 API 的反无人机作战方案自动生成与仿真评估系统。

**本系统仅用于虚拟场景下的方案生成与仿真评估研究，不得用于真实作战指挥或现实行动建议。**

> 本 README 对应交付形态（`military_research/` 已编译为 `.pyd`）。详细使用说明请以
> 《反无人机行动方案智能生成系统_用户指导手册_v4.3.docx》为准，本文件只做索引与快速上手。

---

## 一、系统构成：两套相互独立的子系统

| | A. 方案生成系统（前端） | B. 研究仿真管线 |
|---|---|---|
| 入口 | `main_compiled.py`（命令行交互 / 脚本调用）、`web_app.py`（Streamlit） | `run_military_research.py` |
| 生成方式 | 云端 LLM 单次直调 + 约束检查 | LLM 迭代生成 + 多候选竞争 + EvoPrompt 反思 + 双系统快速规划 |
| Memento 案例记忆 | — | ✅ 500 条案例的 FAISS 向量检索与回写 |
| HOPE 自适应权重 | — | ✅ 条令慢权重 + 仿真快权重 SDE 融合 |
| 仿真评估 | — | ✅ 五阶段杀伤链蒙特卡洛（解析仿真器，非三维物理仿真） |
| LLM 后端 | `config.json`（云端 API） | **优先 `config.json`**；无可用配置时回退本地模型（`LOCAL_LLM_*`，兼容 LM Studio） |
| 依赖模块 | 根目录 5 个 `.pyd` | `military_research/` 下的 `.pyd` 包 |

> 删除 `military_research/` 后，前三种使用方式（交互 / Web / 脚本）仍可正常运行，研究管线与分析工具不可用。

---

## 二、四种使用方式

### 2.1 命令行交互模式
```bash
python main_compiled.py
```

### 2.2 Web 界面模式
```bash
streamlit run web_app.py
# 或
python main_compiled.py --web
```

### 2.3 脚本调用模式
```bash
python main_compiled.py --mission "对敌方无人机集群实施探测、干扰与拦截，确保指挥所安全" \
    --situation sit.txt --assets assets.txt --output plan.json
```
输出为用户方提供的转换模板（`conversion_result.json` 骨架）对应的结构化 JSON：顶层固定
`planId / planName / targetName / generateTime / actionCount / actions`，每个 action 固定 6 个字段
（`dispatchMode / disposalCategory / disposalSubcategory / estimatedDuration / resourceId / startTime`），
且 `actionCount == len(actions)`。

### 2.4 研究仿真管线模式
```bash
# 完整优化管线
python run_military_research.py --scenario data/sample_antidrone.json --iterations 5 --sim-runs 10 --output-dir result/run

# Tier 1 应急预案（零 LLM，毫秒级；必须配 --iterations 0 才会跳过 LLM 迭代）
python run_military_research.py --scenario data/sample_antidrone.json --fast-first --iterations 0 --sim-runs 1

# Tier 2 Delta Loop（以应急预案为锚点做局部补丁）
python run_military_research.py --scenario data/sample_antidrone.json --fast-first --delta-refine --delta-max-iters 12

# 其他加速开关：--single-candidate（单候选）、--rule-based-reflection（规则化反思，零 LLM 反思）
```
`--baseline fewshot_cot|random_search|singlepass_memento` 可运行基线对比；
`--disable-memory / --disable-hope / --disable-reflection / --disable-writeback` 用于消融实验。

---

## 三、安装与配置

### 3.1 安装依赖
```bash
pip install -r requirements.txt
```

- 需要 **Python 3.12**（`.pyd` 全部编译为 `cp312`）。若出现 `DLL load failed` 或
  `Module use of python312.dll conflicts`，请安装 **Visual C++ 运行库**并对齐 Python 版本，
  详见 `环境配置指南.md`。
- 仅在需要重新编译 `.pyd` 时才需 `cython` / `setuptools` / `wheel`。

### 3.2 配置模型 API
```bash
copy config.example.json config.json     # Windows
```
编辑 `config.json` 填入自己的 API Key：
```json
{
  "provider": "deepseek",
  "api_key": "sk-your-api-key-here",
  "model": "",
  "base_url": "",
  "temperature": 0.7,
  "max_tokens": 8000
}
```
- `provider` 可选：`deepseek` / `openai` / `qwen` / `zhipu` / `moonshot` / `siliconflow` / `custom`；
  `model` 留空则使用该服务商默认模型；`base_url` 留空则用公网默认地址。
- 也可用环境变量提供 Key：`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`DASHSCOPE_API_KEY`、
  `ZHIPUAI_API_KEY`、`MOONSHOT_API_KEY`、`SILICONFLOW_API_KEY`。
- **研究管线的回退配置**：未提供可用 `config.json` 时，管线读取 `LOCAL_LLM_BASE_URL` /
  `LOCAL_LLM_API_KEY` / `LOCAL_LLM_MODEL`（默认 `http://localhost:1234/v1`，兼容 LM Studio）。
- `config.json` 含真实密钥，**不要提交到版本库、不要放进交付包**。

---

## 四、装备库与输入文件

### 4.1 `equipment_library.json`（装备库）
定义每种装备的 `resourceId`（输出用短 ID）、处置分类枚举（行为树）与 LLM 匹配用别名：
```json
{
  "name": "T1北部BC波段补盲雷达",
  "aliases": ["BC波段补盲雷达", "YLC-12", "低空补盲雷达"],
  "resourceId": "T1-RADAR-N",
  "type": "探测",
  "disposalCategory": 1,
  "disposalSubcategory": 104,
  "dispatchMode": 1
}
```
新增装备只需在 `"equipment"` 数组里追加一条；已内置 29 条（含 8 条 T1 系列）。

### 4.2 `assets.txt`（我方资源）——支持两种格式
**简洁格式**：
```
JY-17B低空搜索雷达 2部
DWL-200车载电子对抗系统 1套
```
**详细格式**（可带型号/坐标/参数，多条可用 `|` 排在同一行）：
```
探测设备：
-T1北部BC波段补盲雷达(雷达，型号：YLC-12，位置：116.5870°E 40.0846°N,探测距离：5000m) |T1东部频谱侦测端(型号 URD360)
反制设备：
-T1定向干扰端A(定向干扰，型号 DJ-500，2套) |T1网捕站(型号 ZBW-HW03，2具)
```
解析规则：按行与 `|` / `；` 切分条目 → 取「名称区」（第一个括号/逗号之前）在装备库中做**最长匹配**
（名称与别名都参与，不受型号数字与坐标干扰）→ 匹配不到且非分组标题行时才合成条目，并按关键词判断
「探测/反制」、优先用型号串作 `resourceId`。

### 4.3 案例库
`data/memory_bank.jsonl`：500 条反无人机案例（手工标注，含正负样本），供研究管线的 Memento 检索使用。

---

## 五、文件结构

**交付包内容**（`antidrone_delivery 提交版_XX/`）：

```
antidrone_delivery/
├── main_compiled.py                 # 前端主入口（交互 / 脚本）
├── web_app.py                       # Web 界面入口
├── core_imports.py                  # 模块导入兼容层
├── equipment_parser.py              # assets 解析 + 方案 JSON 装配（四种方式共用）
├── run_military_research.py         # 研究仿真管线 CLI 入口
├── build_military_pyd.py            # military_research/ 编译脚本（需要重编译时用）
├── equipment_library.json           # 装备库配置（29 条）
├── config.example.json              # 配置模板（复制为 config.json 使用）
├── requirements.txt
├── sit.txt / assets.txt             # 脚本模式的样例输入
├── evaluator.pyd / llm_interface_cloud.pyd / prompt_templates.pyd /
│   scenario_builder.pyd / utils.pyd # 前端编译模块
├── military_research/               # 研究仿真引擎：13 个裸名 .pyd + __init__.py
├── data/
│   ├── memory_bank.jsonl            # 案例库（500 条）
│   └── sample_antidrone.json        # 示例想定
├── 反无人机行动方案智能生成系统_用户指导手册_v4.3.docx
└── 环境配置指南.md
```

**仅开发仓库（不随交付包发出）**：

```
├── military_research_backup/        # 上述 .pyd 的源码，重新编译与研究用
├── test_equipment_parser.py         # 装备解析自测（22 项断言）
├── smoke_test_delivery.py           # 交付包冒烟测试
├── assemble_delivery_package.ps1    # 交付包组装脚本（含自检与打包）
├── update_manual_v43.py             # 用户手册 v4.3 生成脚本
├── 课题背景知识文档_五场景与仿真原理.docx
└── 反无人机案例库_代表性案例抽样.xlsx
```

---

## 六、自测

```bash
python main_compiled.py --check          # 前端模块编译状态（期望 5/5）
python test_equipment_parser.py          # 装备解析自测（期望全部通过，退出码 0）
python smoke_test_delivery.py            # 交付包冒烟测试（Tier1 零 LLM + 前端自检）
```

---

## 七、支持的服务商

| 服务商 | provider | 默认模型 | 环境变量 |
|---|---|---|---|
| DeepSeek | `deepseek` | deepseek-chat | DEEPSEEK_API_KEY |
| OpenAI | `openai` | gpt-4o | OPENAI_API_KEY |
| 通义千问 | `qwen` | qwen-plus | DASHSCOPE_API_KEY |
| 智谱 GLM | `zhipu` | glm-4-flash | ZHIPUAI_API_KEY |
| 月之暗面 | `moonshot` | moonshot-v1-8k | MOONSHOT_API_KEY |
| 硅基流动 | `siliconflow` | deepseek-ai/DeepSeek-V3 | SILICONFLOW_API_KEY |
| 自定义 / 本地 | `custom` | 手动填写（如 Ollama / LM Studio 的模型名） | CUSTOM_API_KEY |

---

## 八、注意事项

- 本系统仅用于虚拟场景下的方案生成与仿真评估研究，不得用于真实作战指挥或现实行动建议。
- API Key 请妥善保管：不要提交到版本库，不要放进交付包。
- 交付包一律通过 `assemble_delivery_package.ps1` 从仓库组装，避免把开发脚本、缓存、
  测试产物或真实密钥带出去。
