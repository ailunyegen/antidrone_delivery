# 反无人机行动方案智能生成系统

基于云端大模型 API 的反无人机作战方案自动生成与评估系统。

## 功能

- 根据敌方无人机威胁态势，自动生成反无人机 OODA 杀伤链方案
- 支持多种云端大模型（DeepSeek / OpenAI / 通义千问 / 智谱 / Moonshot 等）
- LLM 约束符合性自动评估
- 基于能力模型的五阶段杀伤链仿真评估
- Memento 案例记忆检索（500 条反无人机案例）
- 命令行交互 / Web 界面两种使用方式

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `config.json`，填写你的 API Key：

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

或者设置环境变量：
```bash
set DEEPSEEK_API_KEY=sk-your-api-key-here
```

### 3. 运行

**命令行交互模式：**
```bash
python main.py
```

**Web 界面模式：**
```bash
python main.py --web
```
或直接：
```bash
streamlit run web_app.py
```

**脚本调用模式：**
```bash
python main.py --mission "对敌方无人机蜂群实施拦截" --output result.txt
```

## 支持的服务商

| 服务商 | 默认模型 | 环境变量 |
|--------|---------|---------|
| DeepSeek | deepseek-chat | DEEPSEEK_API_KEY |
| OpenAI | gpt-4o | OPENAI_API_KEY |
| 通义千问 | qwen-plus | DASHSCOPE_API_KEY |
| 智谱 GLM | glm-4-flash | ZHIPUAI_API_KEY |
| 月之暗面 | moonshot-v1-8k | MOONSHOT_API_KEY |
| 硅基流动 | deepseek-ai/DeepSeek-V3 | SILICONFLOW_API_KEY |
| 自定义 | 手动填写 | CUSTOM_API_KEY |

## 文件结构

```
dist_antidrone_system/
├── main.py                 # 主入口（命令行交互/脚本调用）
├── web_app.py              # Web 界面入口
├── config.json             # 配置文件
├── requirements.txt        # Python 依赖
├── llm_interface_cloud.py  # 云端 API 调用封装
├── prompt_templates.py     # 提示词模板
├── evaluator.py            # 评估模块（LLM + 仿真）
├── scenario_builder.py     # 想定解析模块
├── utils.py                # 工具函数
├── data/
│   └── memory_bank.jsonl   # 案例记忆库（500 条反无人机案例）
└── military_research/      # 仿真引擎
    ├── domain.py           # 数据模型
    ├── engine.py           # 仿真器 + HOPE 权重
    ├── case_memory.py      # 案例检索
    └── ...
```

## 注意事项

- 本系统仅用于虚拟场景下的方案生成与仿真评估研究
- 不得将生成内容用于真实作战指挥或现实行动建议
- API Key 请妥善保管，不要泄露给他人
