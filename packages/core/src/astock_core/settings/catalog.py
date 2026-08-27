from __future__ import annotations

from typing import Any

from astock_core.paths import ANALYZE_DIR, DATA_DIR, DB_PATH, DEFAULT_ADJUST, DEFAULT_POOL_ID, QLIB_DIR, system_db_path

SCHEMA_VERSION = 1

INGEST_QUOTES_KEYS = ("pool", "adjust", "sleep")
INGEST_SCHEDULE_KEYS = ("sync_enabled", "sync_time", "timezone")
ANALYZE_LLM_KEYS = (
    "llm_provider",
    "deep_think_llm",
    "quick_think_llm",
    "backend_url",
    "api_key",
)
ANALYZE_GRAPH_KEYS = (
    "output_language",
    "analysts",
    "max_debate_rounds",
    "max_risk_discuss_rounds",
)
ANALYZE_RUNTIME_KEYS = ("temperature", "checkpoint_enabled")


def live_paths() -> dict[str, str]:
    return {
        "data": str(DATA_DIR),
        "db": str(DB_PATH),
        "qlib": str(QLIB_DIR),
        "analyze": str(ANALYZE_DIR),
        "system": str(system_db_path()),
    }


def _section(
    *,
    section_id: str,
    title: str,
    description: str,
    sort_order: int,
    schema: dict[str, Any],
    defaults: dict[str, Any],
    read_only: bool = False,
    computed: bool = False,
) -> dict[str, Any]:
    return {
        "id": section_id,
        "title": title,
        "description": description,
        "sort_order": sort_order,
        "schema": schema,
        "defaults": defaults,
        "read_only": read_only,
        "computed": computed,
    }


def _module(
    *,
    module_id: str,
    title: str,
    description: str,
    sort_order: int,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": module_id,
        "title": title,
        "description": description,
        "sort_order": sort_order,
        "sections": sections,
    }


def settings_catalog() -> list[dict[str, Any]]:
    return [
        _module(
            module_id="ingest",
            title="行情采集",
            description="股票池默认值、复权和盘后同步。quotes.sync 不指定参数时用这里的行情段。",
            sort_order=10,
            sections=[
                _section(
                    section_id="quotes",
                    title="行情",
                    description="默认股票池、复权和两次拉行情之间的间隔。",
                    sort_order=10,
                    defaults={
                        "pool": DEFAULT_POOL_ID,
                        "adjust": DEFAULT_ADJUST,
                        "sleep": 0.35,
                    },
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["pool", "adjust", "sleep"],
                        "properties": {
                            "pool": {
                                "type": "string",
                                "title": "默认股票池",
                                "minLength": 1,
                                "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$",
                            },
                            "adjust": {
                                "type": "string",
                                "title": "复权",
                                "enum": ["", "qfq", "hfq"],
                                "x-widget": "toggle-group",
                                "x-emptyToken": "none",
                                "x-options": [
                                    {"value": "qfq", "label": "前复权"},
                                    {"value": "hfq", "label": "后复权"},
                                    {"value": "", "label": "不复权"},
                                ],
                            },
                            "sleep": {
                                "type": "number",
                                "title": "请求间隔",
                                "description": "两次拉行情之间暂停的秒数。",
                                "minimum": 0,
                            },
                        },
                    },
                ),
                _section(
                    section_id="schedule",
                    title="调度",
                    description="调度器还没接上。先把开关和时间存下来，core 之后按这份配置跑盘后同步。",
                    sort_order=20,
                    defaults={
                        "sync_enabled": False,
                        "sync_time": "16:10",
                        "timezone": "Asia/Shanghai",
                    },
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["sync_enabled", "sync_time", "timezone"],
                        "properties": {
                            "sync_enabled": {
                                "type": "boolean",
                                "title": "盘后自动同步",
                                "description": "每个交易日收盘后按设定时刻提交 quotes.sync。",
                                "x-widget": "switch",
                            },
                            "sync_time": {
                                "type": "string",
                                "title": "同步时刻",
                                "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                                "x-widget": "time",
                            },
                            "timezone": {
                                "type": "string",
                                "title": "时区",
                                "minLength": 1,
                            },
                        },
                    },
                ),
            ],
        ),
        _module(
            module_id="analyze",
            title="TradingAgents",
            description="多智能体分析的 LLM、分析师组合和运行参数。密钥只存在本机系统库，接口不会回传明文。",
            sort_order=20,
            sections=[
                _section(
                    section_id="llm",
                    title="语言模型",
                    description="提供商、模型和密钥。上游内部辩论仍是英文。",
                    sort_order=10,
                    defaults={
                        "llm_provider": "openai_compatible",
                        "deep_think_llm": "",
                        "quick_think_llm": "",
                        "backend_url": "",
                        "api_key": "",
                    },
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "llm_provider",
                            "deep_think_llm",
                            "quick_think_llm",
                            "backend_url",
                            "api_key",
                        ],
                        "properties": {
                            "llm_provider": {
                                "type": "string",
                                "title": "提供商",
                                "enum": [
                                    "openai_compatible",
                                    "qwen-cn",
                                    "deepseek",
                                    "glm-cn",
                                    "ollama",
                                    "openai",
                                ],
                                "x-widget": "select",
                                "x-options": [
                                    {"value": "openai_compatible", "label": "OpenAI 兼容端"},
                                    {"value": "qwen-cn", "label": "通义（国内）"},
                                    {"value": "deepseek", "label": "DeepSeek"},
                                    {"value": "glm-cn", "label": "智谱 GLM（国内）"},
                                    {"value": "ollama", "label": "Ollama"},
                                    {"value": "openai", "label": "OpenAI 官方"},
                                ],
                            },
                            "backend_url": {
                                "type": "string",
                                "title": "接口地址",
                                "description": "OpenAI 兼容端或 Ollama 的 /v1 地址。",
                                "x-visibleWhen": {
                                    "llm_provider": ["openai_compatible", "ollama"]
                                },
                            },
                            "deep_think_llm": {
                                "type": "string",
                                "title": "深度模型",
                            },
                            "quick_think_llm": {
                                "type": "string",
                                "title": "快速模型",
                                "description": "留空则与深度模型相同。",
                            },
                            "api_key": {
                                "type": "string",
                                "title": "API 密钥",
                                "description": "已配置时留空保存不会改密钥。",
                                "x-secret": True,
                                "x-widget": "password",
                            },
                        },
                    },
                ),
                _section(
                    section_id="graph",
                    title="分析图",
                    description="分析师组合、输出语言和辩论轮数。",
                    sort_order=20,
                    defaults={
                        "output_language": "Chinese",
                        "analysts": ["market", "news", "fundamentals"],
                        "max_debate_rounds": 1,
                        "max_risk_discuss_rounds": 1,
                    },
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "output_language",
                            "analysts",
                            "max_debate_rounds",
                            "max_risk_discuss_rounds",
                        ],
                        "properties": {
                            "output_language": {
                                "type": "string",
                                "title": "输出语言",
                                "enum": ["Chinese", "English"],
                                "x-widget": "toggle-group",
                                "x-options": [
                                    {"value": "Chinese", "label": "中文"},
                                    {"value": "English", "label": "English"},
                                ],
                            },
                            "analysts": {
                                "type": "array",
                                "title": "分析师",
                                "minItems": 1,
                                "uniqueItems": True,
                                "items": {
                                    "type": "string",
                                    "enum": ["market", "social", "news", "fundamentals"],
                                },
                                "x-widget": "switch-set",
                                "x-options": [
                                    {"value": "market", "label": "技术"},
                                    {"value": "news", "label": "新闻"},
                                    {"value": "fundamentals", "label": "基本面"},
                                    {
                                        "value": "social",
                                        "label": "情绪",
                                        "description": "依赖 Reddit / StockTwits，A 股几乎没用",
                                    },
                                ],
                            },
                            "max_debate_rounds": {
                                "type": "integer",
                                "title": "辩论轮数",
                                "description": "调大更贵更慢。",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "max_risk_discuss_rounds": {
                                "type": "integer",
                                "title": "风险讨论轮数",
                                "minimum": 1,
                                "maximum": 5,
                            },
                        },
                    },
                ),
                _section(
                    section_id="runtime",
                    title="运行",
                    description="采样温度和断点保存。",
                    sort_order=30,
                    defaults={
                        "temperature": None,
                        "checkpoint_enabled": False,
                    },
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["temperature", "checkpoint_enabled"],
                        "properties": {
                            "temperature": {
                                "type": ["number", "null"],
                                "title": "温度",
                                "description": "留空则用提供商默认。",
                                "minimum": 0,
                                "maximum": 2,
                            },
                            "checkpoint_enabled": {
                                "type": "boolean",
                                "title": "断点保存",
                                "description": "打开后会在缓存目录写 SQLite。同一只票同一天再跑仍是新任务。",
                                "x-widget": "switch",
                            },
                        },
                    },
                ),
            ],
        ),
        _module(
            module_id="qlib",
            title="Qlib",
            description="本地 Qlib 研究框架。行情仍以 market.db 为准，这里管研究和回测默认值。",
            sort_order=30,
            sections=[
                _section(
                    section_id="data",
                    title="数据",
                    description="Qlib 二进制数据目录由仓库根目录决定。region 固定为 A 股规则。",
                    sort_order=10,
                    defaults={"region": "cn"},
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["region"],
                        "properties": {
                            "region": {
                                "type": "string",
                                "title": "市场区域",
                                "enum": ["cn"],
                                "x-widget": "select",
                                "x-options": [{"value": "cn", "label": "A 股（cn）"}],
                            },
                        },
                    },
                ),
                _section(
                    section_id="workflow",
                    title="工作流",
                    description="LightGBM 工作流的市场、基准和回测参数。真正跑任务时再接这些值。",
                    sort_order=20,
                    defaults={
                        "config": "workflow_lightgbm_alpha158",
                        "market": "csi300",
                        "benchmark": "SH000300",
                        "topk": 50,
                        "n_drop": 5,
                        "account": 100000000,
                    },
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "config",
                            "market",
                            "benchmark",
                            "topk",
                            "n_drop",
                            "account",
                        ],
                        "properties": {
                            "config": {
                                "type": "string",
                                "title": "配置模板",
                                "enum": [
                                    "workflow_lightgbm_alpha158",
                                    "workflow_lightgbm_focus5",
                                ],
                                "x-widget": "select",
                                "x-options": [
                                    {
                                        "value": "workflow_lightgbm_alpha158",
                                        "label": "LightGBM + Alpha158",
                                    },
                                    {
                                        "value": "workflow_lightgbm_focus5",
                                        "label": "LightGBM + Focus5",
                                    },
                                ],
                            },
                            "market": {
                                "type": "string",
                                "title": "股票池 / 市场",
                                "minLength": 1,
                            },
                            "benchmark": {
                                "type": "string",
                                "title": "基准",
                                "minLength": 1,
                            },
                            "topk": {
                                "type": "integer",
                                "title": "持仓只数",
                                "minimum": 1,
                                "maximum": 500,
                            },
                            "n_drop": {
                                "type": "integer",
                                "title": "每期换出",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "account": {
                                "type": "number",
                                "title": "回测本金",
                                "minimum": 1,
                            },
                        },
                    },
                ),
            ],
        ),
        _module(
            module_id="system",
            title="系统",
            description="由仓库根目录决定的路径，不能从这里改。",
            sort_order=90,
            sections=[
                _section(
                    section_id="paths",
                    title="路径",
                    description="行情库、Qlib 数据、分析报告和系统库的位置。",
                    sort_order=10,
                    read_only=True,
                    computed=True,
                    defaults=live_paths(),
                    schema={
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["data", "db", "qlib", "analyze", "system"],
                        "properties": {
                            "data": {
                                "type": "string",
                                "title": "数据目录",
                                "readOnly": True,
                            },
                            "db": {
                                "type": "string",
                                "title": "行情库",
                                "readOnly": True,
                            },
                            "qlib": {
                                "type": "string",
                                "title": "Qlib 数据",
                                "readOnly": True,
                            },
                            "analyze": {
                                "type": "string",
                                "title": "分析报告",
                                "readOnly": True,
                            },
                            "system": {
                                "type": "string",
                                "title": "系统库",
                                "readOnly": True,
                            },
                        },
                    },
                ),
            ],
        ),
    ]


def iter_sections() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    items: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for module in settings_catalog():
        for section in module["sections"]:
            items.append((module, section))
    return items


def find_section(module_id: str, section_id: str) -> dict[str, Any]:
    for module, section in iter_sections():
        if module["id"] == module_id and section["id"] == section_id:
            return {"module": module, "section": section}
    raise ValueError(f"未知设置段: {module_id}.{section_id}")
