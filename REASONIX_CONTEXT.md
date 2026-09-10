# REASONIX_CONTEXT.md — 历史工作上下文提炼

> **用途**：给未来的 AI 会话（以及我自己）一份可检索的历史上下文，避免每次重读 5 MB 会话日志。
> **生成方式**：从 `%APPDATA%\reasonix\projects\d--研究生材料-…-antidrone_delivery\sessions\` 下的 5 条会话记录（共 ~6.5 MB）全文提炼，并与当前工作区文件系统逐项核对。
> **核对时间点**：见文末「六、版本谱系与当前差异」——**本文件中的代码结论均以核对时的工作区实况为准，会话记录中的说法若与实况冲突，以「现状核实」一栏为准。**
> **当前状态**：T1（源码回灌）、T2（版本控制整理）、T12（管线接入 config.json + 重编译）、**T13（手册 v4.3）**、**T14（交付包 提交版_05）** 均已落地（提交 `3e5bca4` / `1aea632` / `ec98957` / 本轮，详见「十、本轮落地记录」）；下一步优先项是 **T3**（`_02` 脚手架清理）、**T4**（`assets.txt` 解析兼容）、**T9**（README 过时）。
> **更新规则**：每完成一条「遗留待办」或推翻一条「已定决策」，回来改这里，不要只在对话里说。

---

## 一、项目一句话定位

**反无人机行动方案智能生成系统**（`dist_antidrone_system/antidrone_delivery`）：基于云端大模型 API 自动生成反无人机 OODA 杀伤链方案，并用**独立解析仿真器**做五阶段杀伤链蒙特卡洛评估。用于体系工程学术会议论文 + 毕业设计答辩 + 向合作公司交付可运行软件包。

系统由**两套相互独立**的子系统组成（这是最容易混淆、也是多次反复确认的点）：

| | A. 面向用户的方案生成系统 | B. 研究仿真管线 |
|---|---|---|
| 入口 | `main_compiled.py`（CLI 交互 / 脚本）、`web_app.py`（Streamlit） | `run_military_research.py` → `military_research/` |
| 依赖 | **仅**根目录 5 个 `.pyd`：`scenario_builder` / `evaluator` / `llm_interface_cloud` / `prompt_templates` / `utils` | `military_research/` 13 个模块（12 模块 `.pyd` + `__init__.py`） |
| 生成方式 | LLM **单次直调** + Evaluator 约束检查 | LLM 迭代生成 + 五候选竞争 + Evoprompt 反思 + 门禁回滚 |
| Memento 案例记忆 | ❌ 不用 | ✅ 500 条案例 FAISS 向量检索 + 回写 |
| HOPE 自适应权重 | ❌ 不用 | ✅ 条令慢权重 + 仿真反馈快权重 SDE 融合 |
| 仿真评估 | ❌ 无 | ✅ 五阶段杀伤链蒙特卡洛 |
| 配置 | `config.json` + `CloudLLMClient` | 2026-06 起**也**改为 `config.json` + `CloudLLMClient`（原为环境变量 + 本地 LM Studio） |

> ⚠️ **删掉 `military_research/` 与 `military_research_backup/` 后**：四种方式里的前三种（交互式 / Web / 脚本）**仍可正常运行**，研究仿真管线与分析工具（消融/泛化/对比/可视化）**不可用**。

**四种使用方式**（用户手册第五章骨架，交付验收口径）：
5.1 命令行交互模式 → 5.2 Web 界面模式 → 5.3 脚本调用模式 → 5.4 研究仿真管线模式（提交版_04 起增加快速模式参数）。

---

## 二、四条工作线的时间线

| 话题（reasonix 标题） | 会话文件 | 规模 | 时间跨度 | 干了什么 |
|---|---|---|---|---|
| **代码改动** | `desktop-202606180329-1` | 41 轮 / 3.0 MB jsonl / 11.5 MB events | 记录内 07-17 → 08-26（最后活动） | 主线：代码审查 → 源码 `.pyd` 化 → 手册 v3→v4 → 管线改在线 API → JSON Schema 统一 → 装备库配置化 → 提交版 01→04 → 移植快速规划 |
| **学术汇报** | `20260804-005112…-recovery-d4bfbce872e3c6d6` | 24 轮 / 1.6 MB | 记录内 08-04 → 08-18 | 20 页 PPT + 报告简介（AutoResearch 自主完成）→ 插图 7 轮返工 → 22 页备注重写 → 答辩口径（仿真原理 / 场景化抑制 / 多种子实验）→ 背景知识文档 |
| **git管理** | `desktop-202606250724-1` | 5 轮 | 记录内 06-25 | 合作方报错定位（DLL/内网 IP）→ 环境配置指南 → git init + 首次提交 + 推送 GitHub |
| **统计工作进展** | `desktop-202607060205-1` | 1 轮 | 记录内 07-06 | 只统计进展，无代码改动 |
| （空会话） | `20260806-052137…` | 0 字节 | — | 未使用 |

另有一次 **AutoResearch 自主执行**记录在工作区 `.reasonix/autoresearch/20260804-013528-…-20-p/`：`status: complete`，2 轮结束，交付 `学术汇报.pptx` + `报告简介.docx`（证据 ID `f1`）。

---

## 三、已定技术决策（D 清单）

| # | 决策 | 关键细节 / 理由 |
|---|---|---|
| **D1** | `military_research/` 12 个模块**编译为 Cython `.pyd`（裸名，无平台标签）**交付，源码移入 `military_research_backup/` | 保护源码不直接给合作方；与原有 5 个裸名 `.pyd` 格式统一。用 `build_military_pyd.py --yes` 编译；`military_research/` 最终只留 `__init__.py` + 13 个 pyd |
| **D2** | **研究管线的 LLM 由环境变量改为 `config.json` + `CloudLLMClient`**，与前端统一 | ✅ **T12 已完成（本轮）**。历史情况：该改动曾在一次会话的临时源码里跑通（MS 0.6171），但**从未进入任何提交或交付产物**——T12 前扫描全部 `engine.pyd`，`CloudLLMClient` 计数皆为 0。本轮以更稳健的方式重新落地：`load_llm_config()` + `_CloudChatShim` 适配层，**云端优先、本地回退**，`_chat_json` 与 `DeltaRefiner` 调用点零改动。原 `LocalLLMPlanner` + `LOCAL_LLM_BASE_URL`（默认 `http://localhost:1234/v1`）保留为回退路径 |
| **D3** | **模型名回退必须映射到有效模型名** | `config.json` 中 `"model": ""` 曾回退为字面量 `"deepseek"` → API 报错。正确做法：空值时映射到 `deepseek-chat` / `deepseek-v4-pro` / `deepseek-v4-flash` 之类有效名 |
| **D4** | **输出 JSON 结构以 `conversion_result.json` 为强制模板** | 顶层 6 key 固定：`planId` / `planName` / `targetName` / `generateTime` / `actionCount` / `actions`；每个 action 6 字段：`dispatchMode` / `disposalCategory` / `disposalSubcategory` / `estimatedDuration` / `resourceId` / `startTime`。**取消所有 `.txt` 输出**，四种方式统一产出该骨架 JSON。验收含 `actionCount == len(actions)` |
| **D5** | **处置手段与行为树枚举对齐，分类改为「装备优先」** | 行为树 5 大类枚举（ElectronicJamming/DirectedEnergy/PhysicalCapture/KineticKill/ProtocolHijack）；项目补齐缺失的 **GNSSJamming(101)**；`_classify_action` 由「关键词」改为**先按装备名判定**，修掉 `JY-17B低空搜索雷达` 被误判为「遥控信号干扰(103)」的问题（现归「雷达干扰(104)」） |
| **D6** | **`EQUIPMENT_ID_MAP` 从硬编码抽为 `equipment_library.json` 配置文件** | 原硬编码在两处（`main_compiled.py` 的 `build_structured_plan_json()` 与 `web_app.py` 的 `_build_structured_plan_json_web()`），重复代码。现由 `_load_equipment_library()` / `_match_equipment()` 统一加载；**加内存缓存**（CLI/脚本/管线用模块级全局变量，Web 用 `st.session_state`）避免每次请求读盘 |
| **D7** | **交付包与工作目录分离，提交版按序递增** | `antidrone_delivery 提交版_01 … _04` + 对应 `.rar`；交付前必做：清真实 API Key 与内网 IP、清 `__pycache__`、清带平台标签的 `.pyd`、清测试产物。`config.example.json` 只留占位符 |
| **D8** | **移植「缩短方案生成时间」能力到反无项目（提交版_04）** | 自 `Memento-military` 项目移植 `fast_pipeline.py` + `cli.py` 6 个新参数：`--fast-first`（Tier1 零 LLM 应急预案，案例骨架继承 + HOPE 权重投影 + 兵力缩放，实测 **12.1 ms**）、`--delta-refine`（Tier2 Delta Loop：瓶颈定位 + LLM 只重写瓶颈阶段 + 门禁回滚）、`--single-candidate`、`--rule-based-reflection`、`--delta-max-iters`、`--early-stop-ms`。**约束：不修改现有功能** |
| **D9** | **合作方环境对齐口径**：Python **3.12** + MSVC 运行库 | `.pyd` 全部为 `cp312`，且依赖 `vcruntime140.dll`；合作方报错 `DLL load failed` + `Module use of python312.dll conflicts` 即此因。已产出 `环境配置指南.md` 并更新 `requirements.txt` |
| **D10** | **版本控制**：`git init` → 单次提交 `e144230`（71 files, 8821 insertions）→ 推送到 `git@github.com:ailunyegen/antidrone_delivery.git` | **HTTPS(443) 被当前网络拦截，必须走 SSH**。`.gitignore` 排除：`config.json`（含 Key）、`output/`、`result/`、`__pycache__/`、`.reasonix/`、`*.bak`、`build/`、`temp/`、`*.c` |

---

## 四、已定结论（C 清单 — 答辩 / 对合作方 / 对导师的口径）

| # | 结论 | 支撑事实 |
|---|---|---|
| **C1** | **仿真的执行者不是大模型** | LLM 只负责「方案生成」；方案一旦变成结构化 JSON，评估完全由独立解析仿真器 `PlanSimulator`（`engine.py`）完成，LLM 不参与任何战场推演。这是回答导师「比 AFSIM 可靠性」质疑的核心前提 |
| **C2** | **可靠性论证路线**：解析计算 + 蒙特卡洛 + 案例锚定，而非三维物理仿真 | 阶段评分公式、随机性来源、能力聚合均为确定代码；`main_blinded.pdf` Discussion 提供效应量与显著性的表达口径 |
| **C3** | **技术栈：原生 Python 编排，未用任何 Agent 框架** | `langchain` / `autogen` / `langgraph` / `llama_index` / `crewai` 全部未引入（requirements 与全源码 import 已核实）；「生成→评估→反思→迭代」循环是手写在 `MilitaryResearchPipeline` 里 |
| **C4** | **「场景化抑制」= 反思模块被自动关闭的机制** | `_suppress_reflection_for_scene()` 对四类场景**无条件**关闭反思（如江河突击 `assault`+`river`、山地侦察等），另有 `_should_use_reflection()` 的条件抑制层 |
| **C5** | **案例库（`data/memory_bank.jsonl`，500 条）结构与覆盖优秀，但内容模板化严重** | 100% 手工标注 `AD-xxxx`、11 字段 100% 完整、时间戳 100%（2024-01 ~ 2025-05）、正 338 : 负 162 = 68% : 32%、7 地形 × 4 任务 × 18 装备 × 12 敌情；**但 1338 条 Lessons 去重后仅 30 条** → 已抽样 20 条导出 `反无人机案例库_代表性案例抽样.xlsx` 请专业人士评审（三种工作表，正例绿底/负例橙底） |
| **C6** | **多种子实验设计** | 种子 `{7, 42, 123, 999, 2024}`；固定想定/迭代/蒙特卡洛/案例库仅换种子；配对 t 检验 `df=4`、`p<0.01`、报告 Cohen's d；另有优化参数下 3 种子补充复跑 |
| **C7** | **可复现的样本指标**（供回归比对） | 管线「反无人机蜂群防御作战」：`mission_success 0.6171` / `ler 0.773` / `completion_time_hours 12.09` / `overall_effectiveness 0.655`；基线模式 `0.5825 / 0.6297`；提交版_04 Tier1 应急预案 `0.6041`（退出码 0、零 LLM 调用）；消融结论 `ΔMS +4.47`、`ΔOE +6.83`、`ΔLER +37%`，跨场景 **5/5 全胜** |
| **C8** | **五个泛化场景（论文 Table 6/7 为准）** | 沿海联合突击 / 城市枢纽防御 / 山地走廊侦察 / 渡河突破 / 岛屿补给走廊保障；系统想定中「兵力数量」为确定值，**具体装备清单论文未逐条给出**，汇报时须标注「示例构成」 |
| **C9** | **资源 ID 提取是三层链路** | ① `assets.txt` 装备行 → ② `_find_resource_id()` 在装备映射表做**子串匹配**（未命中则取行首 12 字符兜底）→ ③ `_parse_actions_from_plan()` 在 LLM 方案章节中交叉匹配。**已知脆弱点见 T4** |
| **C10** | **数据库演进建议（仅设计，未实施）** | 推荐 **SQLite 单文件**（零安装、零配置、随包交付、Python 标准库自带）；表结构含 `equipment` / 案例库 / 方案产物等，装备表字段与 `equipment_library.json` 对齐（见 T5） |

---

## 五、遗留待办（T 清单，按优先级）

### 🔴 高优先（会直接影响交付 / 复现）

| # | 待办 | 现状核实 |
|---|---|---|
| **T1** | ✅ **已完成**（提交 `3e5bca4`）——把 `_02` 的最新源码与编译产物回灌仓库 | 已回灌并逐字节校验一致：`main_compiled.py`（15,779→22,567）、`web_app.py`（7,808→12,683）、`military_research_backup/{engine.py, cli.py}`、新增 `fast_pipeline.py`；`military_research/{engine,cli}.pyd` 更新 + 新增 `fast_pipeline.pyd`（与 `提交版_04` MD5 一致）；新增 `equipment_library.json`、`sit.txt`、`assets.txt`。**回归验证**：14 个模块 import OK（裸名 `.pyd` 亦可）、`--fast-first --iterations 0` 复现 `mission_success=0.6041`、前端 `--check` 5/5、`py_compile` 通过 |
| **T2** | ✅ **已完成**（提交 `1aea632`）——版本控制范围整理 | 仓库**私有**（已确认）→ `military_research_backup/` 保持跟踪、不改写历史。`.gitignore` 新增 `_kaiti_imgs/`、`_kaiti_pdf_imgs/`、`main_blinded.pdf`、`*.cp312-win_amd64.pyd`；**取消跟踪 24 个平台标签 `.pyd`**（本地文件保留，克隆后仅裸名 `.pyd`，已验证可正常 import）；纳入手册 v4.1/v4.2、`课题背景知识文档_五场景与仿真原理.docx`、`build_knowledge_doc.py`、`add_multiseed_section.py`、`REASONIX_CONTEXT.md`。跟踪文件 71 → **58**，工作树干净 |
| **T3** | **`_02` 里大量一次性脚手架脚本未清理**，不可进入交付包 | `patch_engine.py`、`patch_engine2.py`、`patch_return.py`、`fix_defaultdict.py`、`fix_all_defaultdict.py`、`assemble_v04.py`、`sync_v04.py`、`prep_cli.py`、`prep_recompile.py`、`check_engine.py`、`check_tier1.py`、`e2e_*.py`、`inspect_v41.py`、`update_manual_v42.py`、`verify_*.py`、`clean_sources.py` |
| **T4** | **`assets.txt` 装备解析格式兼容未彻底解决** | 解析假设格式为 `装备名 数量`（用 `re.split(r'\s+\d+', line)[0]`）；用户实际提供的 `T1北部BC波段补盲雷达(雷达，型号：YLC-12 C波段低空补盲雷达，位置：…)` 会被切错。装备库已补 T1 系列别名（共 29 条），但**是否已改用更稳健的匹配（如「库中名称/别名子串包含」优先于分词）未见收尾验证** |
| **T5** | 数据库方案未落地 | 仅为 U40 的设计回答（SQLite 表结构），无代码、无迁移脚本 |
| **T5b** | ✅ **已澄清（T2 期间确认）**：仓库为**私有**仓库 | 用户确认 `ailunyegen/antidrone_delivery` 为私有，故 `military_research_backup/` 12 个 `.py` 源码**保持跟踪、不改写历史**（e144230 无需 filter-repo）。若日后仓库转公开，必须重提本项。**注：从本机无法直连 GitHub API 核实可见性（HTTPS 443 被拦），结论依据用户确认。** |
| **T12** | ✅ **已完成**（本轮）——管线改用 `config.json` + `CloudLLMClient`，并重编译 | 在 `engine.py` 增加 `load_llm_config()`（查找顺序：显式路径 → cwd → 项目根；api_key 支持环境变量兜底）与 `_CloudChatShim`（把 `CloudLLMClient.generate_json()` 适配成 `chat.completions.create()`，从而**不动** `_chat_json` 及下游 `DeltaRefiner`）；`LocalLLMPlanner.__init__` 先试云端、失败或无配置时**自动回退本地** `LOCAL_LLM_*`。**验证**：后端探测 `cloud / deepseek / deepseek-chat / https://api.deepseek.com/v1`；真实 API 调用返回合法 JSON；`--iterations 1 --single-candidate` 全流程走云端跑通（MS 0.6412 / LER 0.8307 / OE 0.6717，exit 0）；无 config 时回退 `local / http://localhost:1234/v1`；Tier1 零 LLM 仍为 **0.6041**；前端 `--check` 5/5；运行清单已正确记录 `api_mode=cloud-json (deepseek)`、`source=config.json` |
| **T13** | ✅ **已完成**（手册 v4.3） | `update_manual_v43.py` 以 v4.2 为源生成 `反无人机行动方案智能生成系统_用户指导手册_v4.3.docx`（57,887 B），共 9 处修改：封面版本号、§5.4 新增「模型接入（v4.3）」段（优先 `config.json`、未配置回退 `LOCAL_LLM_*`）、§5.6 Tier1 补「无需 API Key 也不需要本地模型服务」、§6.1 说明该配置由前端与管线共用、§6.5 补管线回退用的本地模型环境变量、版本历史新增 v4.3 条、最后更新日期、附录版本表新增 v4.3 行、命令速查表新增研究管线命令。**回读校验 9/9 项命中** |
| **T14** | ✅ **已完成**（交付包 提交版_05） | 以 `提交版_04` 为基线组装 `antidrone_delivery 提交版_05`（34 文件）+ `antidrone_delivery 提交版_05.rar`（1,439,566 B，`rar t` 全部正常）。替换 `military_research/engine.pyd`（947,712 B，支持 config.json）与手册 v4.3；清理 `__pycache__` / 历史手册 / 平台标签 `.pyd` / `.bak` / `config.json`。**包内实测**：Tier1 零 LLM `0.6041`；临时放入 config.json 后云端全流程跑通（MS 0.6394 / LER 0.8479 / OE 0.6725，`llm_backend.api_mode=cloud-json (deepseek)`、`source=config.json`）；前端 `--check` 5/5；验证后已清除临时 config.json、result/、`__pycache__` |

### 🟡 中优先（一致性与整洁）

| # | 待办 |
|---|---|
| **T6** | ✅ 已完成（随 T2）——手册版本回同步 | 已把 `用户指导手册_v4.1.docx`（来自 `_02`）与 **`v4.2.docx`（来自 `提交版_04`，最新）** 复制进工作区并提交；仓库现同时持有 v3.0 / v4.0(docx+pdf) / v4.1 / v4.2。已核验 v4.2 内文：Tier1/Tier2 参数、`--fast-first --iterations 0` 零 LLM 用法、`fast_pipeline.pyd` 与 `equipment_library.json` 均在手册中 |
| **T7** | 合作方环境问题闭环确认：`DLL load failed` / `python312.dll conflicts` 是否已按 `环境配置指南.md` 解决；`config.example.json` 的内网 IP `http://10.109.6.4:1234` 已清除（现为 `base_url: ""`），需确认合作方拿到的包也是新版 |
| **T8** | 工作区 `.reasonix/` 残留可清理：3 个 `truncated-results/*.txt` 是乱码日志（GBK/UTF-8 串码），1 个 `attachments/*.pdf` 未处理（已 gitignore，不影响仓库） |
| **T9** | `README.md` 内容已过时：仍写 `main.py`、`python main.py --web`、目录树为 `.py` 源码版，且只提「两种使用方式」。需按 `.pyd` + 四种方式重写 |

### 🟢 记录级（不影响运行）

| # | 待办 |
|---|---|
| **T10** | 「统计工作进展」线只有 1 轮，无产出；「新的会话」为空会话，可在 reasonix 里清理 |
| **T11** | 提交版 `_02` 目录已不存在（只剩 `提交版_02.rar`），如后续要对比需从 rar 解出 |

---

## 六、版本谱系与当前差异（核对实况）

**提交版谱系**（父目录 `dist_antidrone_system\`）：

| 交付包 | 状态 | 关键内容 |
|---|---|---|
| `提交版_01`（+rar） | 旧 | 首次交付（含 API Key 残留风险期） |
| `提交版_02.rar`（目录已删） | 旧 | JSON 导出四方式闭环（`main_compiled.py` 加 `build_plan_json()`、Web 加导出按钮） |
| `提交版_03`（+rar） | 旧 | 装备库配置化（`equipment_library.json`）+ 手册 v4.1 + `sit.txt`/`assets.txt` |
| `提交版_04`（+rar） | 旧（前基线） | 含 `fast_pipeline.pyd`、`cli.pyd`（6 个快速模式参数）、手册 v4.2、`equipment_library.json`、`sit.txt`/`assets.txt`、`环境配置指南.md` |
| **`提交版_05`（+rar）** | **最新交付（T14）** | 相对 04 的差异：`engine.pyd` 换成支持 `config.json` 的新版（947,712 B）、手册升到 **v4.3**；其余不变。已在包内实测 Tier1（0.6041）、云端全流程、前端自检 |

**工作目录三处对照（T1 落地后已更新）**：

| 项 | `antidrone_delivery`（当前工作区 / git 仓库） | `antidrone_delivery_02`（开发工作台，含脚手架） | `提交版_04`（交付包） |
|---|---|---|---|
| 角色 | ✅ **现已是唯一权威源码与产物仓库** | 开发/编译工作台（脚手架脚本待清理，T3） | 干净交付包 |
| `fast_pipeline.py` / `.pyd` | ✅ 31,323 B / 252,416 B | ✅ 同 | ✅ `fast_pipeline.pyd` 同 |
| `engine.py`（备份源码） | ✅ 159,715 B（新） | 159,715 B（同） | —（仅 pyd，871,424 B） |
| `cli.py` | ✅ 8,098 B（含 6 个快速参数） | 8,098 B（同） | `cli.pyd` 69,632 B（MD5 同） |
| `main_compiled.py` | ✅ 22,567 B（Schema 重构后） | 22,567 B（同） | 22,567 B（同） |
| `web_app.py` | ✅ 12,683 B | 12,683 B（同） | 12,683 B（同） |
| `engine.pyd` / `cli.pyd` | ✅ `engine.pyd` 947,712 B（T12 后领先交付包基线）；`cli.pyd` 与 `提交版_04` MD5 一致 | 同（engine 为旧版） | **`提交版_05`：engine 947,712 B（同仓库）** |
| 手册 | ✅ v3.0 / v4.0(docx+pdf) / v4.1 / v4.2 / **v4.3** | v4.0 / v4.1 | 提交版_04: v4.2；**提交版_05: v4.3** |
| `equipment_library.json` | ✅ 8,336 B（29 条，**已入库**） | ✅ 同 | ✅ 同（MD5 一致） |
| 平台标签 `.pyd` | ⚠️ 本地保留但**已不受版本控制**（T2） | 仍保留且未忽略 | 无（交付包只留裸名） |

> **一句话（T1 前）**：工作区曾是「Schema 重构 + 快速规划移植」之前的快照，最新成果在 `提交版_04`、最新源码在 `_02`。
> **一句话（T1 后）**：三者对**核心源码与编译产物已逐字节一致**，仓库可直接作为后续开发与出包的唯一基线；`_02` 退回为临时工作台（其脚手架脚本见 T3）。

**`equipment_library.json` 结构**（29 条装备）：

```json
{
  "_comment": "name=装备全称, aliases=LLM可能使用的别名, resourceId=输出用短ID, type=探测/反制, disposalCategory/disposalSubcategory/dispatchMode=行为树枚举值",
  "equipment": [
    { "name": "T1北部BC波段补盲雷达",
      "aliases": ["BC波段补盲雷达", "YLC-12", "C波段低空补盲雷达", "补盲雷达", "低空补盲雷达"],
      "resourceId": "T1-RADAR-N", "type": "探测",
      "disposalCategory": 1, "disposalSubcategory": 104, "dispatchMode": 1 }
  ]
}
```
含用户方 8 种 T1 系列装备（5 探测 + 3 反制，含型号别名）+ 原有预定义装备，合计 29 条。

---

## 七、已知坑（踩过的，别再踩）

1. **Cython 严格类型**：把 `defaultdict` 赋给带 `dict` 注解的变量会炸（`_aggregate_capabilities` 等）。修法：改普通 `dict` + `.setdefault()`。**此类 bug 在编译后才暴露，源码里看不出来。**
2. **中文长路径 > 260 字符**：MSVC 链接失败（`export_generalization_case_banks` 文件名过长时必炸）。修法：编译脚本用**短临时目录 + 逐文件独立编译**，避免嵌套。
3. **GBK 终端打印 `✓` 会崩**：编译脚本输出字符要 ASCII 安全。
4. **大文件多次「替换式编辑」会把文件改坏**：`engine.py` 曾被 6 次以上替换污染，**丢失 `PlanGenerator` / `PlanSimulator` / `MilitaryResearchPipeline` 三个类**。教训：先备份、用一次性脚本批量应用补丁、改完立刻编译校验类是否都在。
5. **目标文件被占用**：PPT/Word 被 PowerPoint/Word 打开时保存失败 → 先写临时文件，验证后再覆盖。
6. **`_02` 的 `engine` 是本地 LLM 版（环境变量）**，跨目录移植时会缺 `exporters` 模块、`_aggregate_capabilities` 返回 `defaultdict` —— 移植前必须先对齐版本，否则"回归通过"是假象。
7. **无 git 仓库时无法做「审查最近一次提交」**：首次会话就卡在这。
8. **HTTPS 推 GitHub 不通**（443 被拦），只能用 SSH；远端 `origin` 现已是 SSH 形式。
9. **`config.json` 含真实 API Key**，已被 gitignore + 提交版清除；`.env`（`%APPDATA%\reasonix\.env`）亦属敏感，勿读勿传。
10. **在本机 DSH 沙箱内重编译 `.pyd` 的三个坑（T12 实测）**：
    - python 子进程的**删除操作被沙箱拒绝**（`os.remove` / `shutil.rmtree` 报 `PermissionError`，工作区内也一样），而 `build_military_pyd.py` 必须删除重建临时目录并覆盖既有 `.pyd` → 需以 `danger-full-access` 运行编译命令；
    - `TEMP` 必须指向**工作区内**目录（harness 的临时目录对 python 子进程不可写），例如 `$env:TEMP=(Join-Path (Get-Location) 'temp')`；
    - TEMP 路径一深，三个长模块名（`export_generalization_case_banks` / `summarize_generalization` / `summarize_multiseed_ablation`）就会 `LNK1104` 链接失败 → 若需整包重编，用浅层 TEMP（如 `C:\pydtmp`）。**只改 `engine.py` 时可只把该文件放进 `military_research/` 再编译，避开长名模块。**
11. **写 `.ps1` 脚本必须存成 UTF-8 with BOM**：Windows PowerShell 5.1 对无 BOM 的 UTF-8 按 ANSI 解析，脚本里的中文（含中文文件名）会乱码并报 `Unexpected token` 语法错误。转换：`$c=Get-Content x.ps1 -Raw -Encoding UTF8; Set-Content x.ps1 -Value $c -Encoding UTF8`。
12. **打包交付包用 WinRAR 控制台版**：`D:\Program Files\WinRAR\Rar.exe`（本机无 7-Zip）。整包重编与交付包组装都写在仓库脚本里：`build_military_pyd.py`、`assemble_delivery_package.ps1`（支持 `-Version`/`-BaseVersion` 参数复用于下一版）。

---

## 八、原始记录位置与提取方法（需要深挖时用）

**本项目在 reasonix 里的记录（对话正文不工作区里）**：

```
C:\Users\Alcoholic\AppData\Roaming\reasonix\projects\
  d--研究生材料-论文汇总-体系工程学术会议-kill_chain_project-初稿-dist_antidrone_system-antidrone_delivery\
    sessions\
      desktop-202606180329-1.jsonl              ← 「代码改动」41 轮（主战场）
      desktop-202606250724-1.jsonl              ← 「git管理」
      desktop-202607060205-1.jsonl              ← 「统计工作进展」
      20260804-005112.641612900-…-d4bfbce872e3c6d6.jsonl  ← 「学术汇报」
      *.events.jsonl / *.display-index.json / *.goal-state.json  ← 事件流、渲染索引、目标状态
```

**话题 ↔ 会话映射**：`%APPDATA%\reasonix\desktop-projects.json`（本项目 5 个 topic id）。
**工作区 `.reasonix/`**：只有话题标题元数据、AutoResearch 状态、被截断的工具输出与一个附件 PDF —— **不是对话记录**，且已被 `.gitignore` 排除。

**快速提取「人提了什么要求」的 PowerShell 片段**（会话 jsonl 每行一个 `{role,id,content}`）：

```powershell
$p="$env:APPDATA\reasonix\projects\d--研究生材料-论文汇总-体系工程学术会议-kill_chain_project-初稿-dist_antidrone_system-antidrone_delivery\sessions"
foreach($l in (Get-Content -LiteralPath (Join-Path $p 'desktop-202606180329-1.jsonl') -Encoding UTF8)){
  if(-not $l.Trim()){continue}
  try{$o=$l|ConvertFrom-Json}catch{continue}
  if($o.role -in @('user','assistant')){
    $c=$o.content; if($c -isnot [string]){$c=($c|%{if($_.text){$_.text}else{''}})-join ' '}
    $c=($c -replace '(?s)<reasoning-language>.*?</reasoning-language>','') -replace '\s+',' '
    if($c){ "{0}: {1}" -f $o.role, $c.Substring(0,[Math]::Min(200,$c.Length)) }
  }
}
```
> 注意：必须 `-Encoding UTF8`（默认按 ANSI 读会乱码）；同一行可能有多个 assistant 片段（工具调用间的过渡语），最后一条才是本轮结论。

---

## 九、安全与合规红线

- **仅供虚拟场景下的方案生成与仿真评估研究**；不得用于真实作战指挥或现实行动建议（README 已声明，交付包保留）。
- `config.json` / `.env` 含真实 API Key：**不入库、不进交付包、不写入本文档**。
- 内网地址 `http://10.109.6.4:1234` 属开发者内网，交付前必须清除（现 `config.example.json` 已为空串）。
- `military_research/` 源码不直接交付给合作方（D1）；`military_research_backup/`（12 个 `.py` 源码）**已随 `e144230` 推送到 GitHub，且仓库经确认为私有**（T2/T5b），因此保持跟踪、不改写历史。**若仓库日后转公开，必须立即处理该项。**

---

## 十、本轮落地记录（T1 / T2）与新增发现

**执行时间**：本轮会话（`REASONIX_CONTEXT.md` 同期）。**基线**：`e144230`（初始提交）→ 落地后 `3e5bca4`（T1）→ `1aea632`（T2）。

### 10.1 做了什么

| 提交 | 内容 |
|---|---|
| `3e5bca4` **T1** | 从 `antidrone_delivery_02` 回灌：`main_compiled.py`、`web_app.py`、`military_research_backup/{engine.py, cli.py, fast_pipeline.py}`、`military_research/{engine.pyd, cli.pyd, fast_pipeline.pyd}`（+ 平台标签版）、`equipment_library.json`、`sit.txt`、`assets.txt` |
| `1aea632` **T2** | `.gitignore` 新增 4 类忽略项；取消跟踪 24 个平台标签 `.pyd`；纳入手册 v4.1/v4.2、`课题背景知识文档_五场景与仿真原理.docx`、`build_knowledge_doc.py`、`add_multiseed_section.py`、本文件 |

### 10.2 验证证据（可复跑）

```powershell
# 1) 14 个模块导入（含裸名 .pyd 场景）
python -c "import military_research.engine, military_research.cli, military_research.fast_pipeline; print('ok')"
# 2) Tier1 零 LLM 应急预案 —— 期望 mission_success = 0.6041（与 提交版_04 记录一致）
python run_military_research.py --fast-first --iterations 0 --sim-runs 1 --output-dir result
#    ⚠️ 必须带 --iterations 0，否则 Tier1 之后仍会跑默认 3 轮 LLM 迭代
# 3) 前端模块自检 —— 期望 5/5 已编译
python main_compiled.py --check
# 4) 装备库 —— 期望 29 条
python -c "import json;print(len(json.load(open('equipment_library.json',encoding='utf-8'))['equipment']))"
```

结果：① 14/14 OK（临时移开全部平台标签 `.pyd` 后仍 OK，证明**克隆后仅裸名 `.pyd` 亦可运行**）；② `0.6041`；③ 5/5；④ 29。`git status` 干净，跟踪文件 71 → 58。

### 10.3 新增发现（重要）

1. **D2 从未落地（T12）**：扫描 `提交版_01/_03/_04`、`_02`、当前仓库的 `engine.pyd`，`CloudLLMClient` 出现次数**全为 0**、`LocalLLMPlanner` 均存在。**结论：管线始终走本地 LM Studio（`http://localhost:1234/v1`），与前端 `config.json` 双轨并存**；干净机器上非 Tier1 路径会 `502` 失败。会话记录里 U16 那次「管线跑通（MS 0.6171）」用的临时源码版本未被任何产物继承。
2. **Tier1 语义澄清**：`--fast-first` 只是把应急预案作为**起点**，`run()` 仍执行 `for iteration in range(iterations)`。零 LLM 需 `--fast-first --iterations 0`。**手册 v4.2 已正确写明该用法**（无需修改手册）。
3. **仓库结构冗余已消除**：此前仓库同时跟踪裸名与平台标签 `.pyd`（24 个重复文件），现只保留裸名；`提交版_04` 亦只含裸名，两者一致。
4. **`提交版_04` 与仓库核心产物 MD5 一致**：`engine.pyd` / `cli.pyd` / `fast_pipeline.pyd` / `equipment_library.json` / `main_compiled.py` / `web_app.py` 全部逐字节相同 —— 仓库现在是**可复现出交付包**的基线。（⚠️ T12 之后 `engine.pyd` 已领先于 `提交版_04`，见 T14。）

### 10.4 T12：管线接入 config.json 云端 API（本轮）

**改了什么**（源码 `military_research_backup/engine.py`，168,521 B）：

| 新增/修改 | 作用 |
|---|---|
| `load_llm_config()` | 读取与前端共用的 `config.json`（`provider/api_key/model/base_url/max_tokens`）；查找顺序 显式路径 → cwd → 项目根；api_key 支持 `DEEPSEEK_API_KEY` 等环境变量兜底；**无可用配置返回 `None`**；结果带缓存 |
| `_project_root()` | 兼容源码运行与 `.pyd` 运行（`__file__` 的上级目录） |
| `_CloudChatShim` / `_CloudChatNamespace` / `_CloudCompletions` | 把 `CloudLLMClient.generate_json()` 适配成 `client.chat.completions.create(...)`，**`_chat_json` 与 `DeltaRefiner._chat_json` 调用点零改动** |
| `LocalLLMPlanner.__init__` | 先试云端（`init_cloud_client`，空 model 自动解析为服务商默认模型）；不可用时**静默回退**原有 `LOCAL_LLM_*` 本地路径；新增 `self.backend` / `self.provider` |
| `_collect_runtime_manifest()` | 运行清单如实记录 `model_id` / `base_url` / `api_mode`（`cloud-json (deepseek)` 或 `openai-compatible`）/ `source` |
| `_chat_json` 报错信息 | 由「Local LLM failed…」改为含 `backend=` 的通用描述 |

**验证矩阵（全部实跑）**：

| 用例 | 期望 | 实测 |
|---|---|---|
| 后端探测 | cloud + 服务商默认模型 | `cloud / deepseek / deepseek-chat / https://api.deepseek.com/v1` ✅ |
| 真实 API 调用（经 shim） | 返回合法 JSON | `{"ok": true, "note": "连通性测试"}` ✅ |
| 全流程云端跑通 `--iterations 1 --single-candidate` | 产出方案与报告 | exit 0；**MS 0.6412 / LER 0.8307 / 12.5h / OE 0.6717**；运行清单 `api_mode=cloud-json (deepseek)`、`source=config.json` ✅ |
| 无 config.json 时回退 | `local / http://localhost:1234/v1` | ✅ |
| Tier1 零 LLM（`--fast-first --iterations 0`） | 0.6041（与 T1 一致） | ✅ 0.6041 |
| 前端 `main_compiled.py --check` | 5/5 | ✅ 5/5 |

**产物**：`military_research/engine.pyd` 871,424 B → **947,712 B**（平台标签镜像同步）；`military_research/engine.py` 编译后已删除，包内保持「仅 `.pyd` + `__init__.py`」的交付形态。其余 9 个未改源码的 `.pyd` 已从 git 还原（保持 `提交版_04` 同源产物），因此本次提交**只有 engine 一项二进制变化**，便于审计。

### 10.5 T13 / T14：手册 v4.3 与交付包 提交版_05（本轮）

**T13 — 手册 v4.3**（`update_manual_v43.py`，以 v4.2 为源，python-docx 脚本化修改，可重跑）：

| # | 位置 | 修改 |
|---|---|---|
| 1 | 封面 | `版本： v4.2` → `v4.3` |
| 2 | §5.4 | 新增「模型接入（v4.3）」段：管线优先读与前端同一份 `config.json`；无可用配置时回退 `LOCAL_LLM_BASE_URL / LOCAL_LLM_API_KEY / LOCAL_LLM_MODEL`（默认 `http://localhost:1234/v1`） |
| 3 | §5.6 | Tier1 说明补「无需 API Key，也不需要本地模型服务」 |
| 4 | §6.1 | 说明 `config.json` 由前端（命令行/Web/脚本）与管线共用 |
| 5 | §6.5 | 补充管线回退用的本地模型环境变量（与云端 Key 环境变量相互独立） |
| 6-8 | 版本历史 / 页脚 / 附录版本表 | 新增 v4.3 条目，更新最后更新日期，版本表在最上方插入 v4.3 行 |
| 9 | 附录A 命令速查 | 新增研究管线命令行 |

回读校验：9/9 命中（`paragraphs 349→353`，`tables 14` 不变）。**注意 python-docx 插入段落用 `deepcopy(anchor._p)` + `addnext/addprevious` 才能继承原样式；表格行需 `tbl.remove(tr)` 后 `header.addnext(tr)` 才能插到表头之后。**

**T14 — 交付包 提交版_05**（`assemble_delivery_package.ps1 -Version 05 -BaseVersion 04`，脚本已参数化，下一版直接改版本号）：

```
antidrone_delivery 提交版_05/          34 个文件
├── main_compiled.py / web_app.py / core_imports.py / run_military_research.py
├── build_military_pyd.py / equipment_library.json / sit.txt / assets.txt
├── config.example.json / requirements.txt / README.md / 环境配置指南.md
├── 5 个前端 .pyd（evaluator / llm_interface_cloud / prompt_templates / scenario_builder / utils）
├── military_research/ 13 个裸名 .pyd + __init__.py（engine.pyd = 947,712 B，支持 config.json）
├── data/（memory_bank.jsonl 500 条 + sample_antidrone.json）
└── 反无人机行动方案智能生成系统_用户指导手册_v4.3.docx
```

**包内实测（在交付包目录内运行，非工作区）**：

| 用例 | 实测 |
|---|---|
| Tier1 零 LLM（无 config.json） | `mission_success 0.6041` / LER 0.7129 ✅ |
| 临时放入 config.json 后云端全流程 | exit 0；MS 0.6394 / LER 0.8479 / OE 0.6725；`llm_backend.api_mode=cloud-json (deepseek)`、`model_id=deepseek-chat`、`source=config.json` ✅ |
| 前端 `main_compiled.py --check` | 5/5 ✅ |
| 交付包自检 | 无 `config.json` / 无平台标签 `.pyd` / 无 `__pycache__` / 无 `.bak` / 无 `.c` ✅（验证后临时 config.json、`result/`、`__pycache__` 已清除） |
| 压缩件 | `antidrone_delivery 提交版_05.rar` 1,439,566 B，`rar t` 全部正常；条目数 37 = 34 文件 + 2 目录 + 1 根条目（与 04 的 39 = 35+3+1 同构） |
