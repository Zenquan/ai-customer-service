# server · 智能客服后端

> 校准日期：2026-10-14。代码直接位于 `src/`，Python 导入包为 `src`，发行包名称仍为 `server`；运行数据以 `SERVER_HOME` 或启动时的当前目录为根。

FastAPI API、RAG Core、LangGraph 客服图、演示认证与订单工具、MySQL/内存存储和评测组件。

## 安装与启动

以下命令从仓库的 `server/` 目录执行：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[local]' --group dev
cp .env.example .env
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000 --workers 1
```

`local` 是 FastEmbed 可选 extra，`dev` 是 pytest 依赖组；不存在 `[dev]` extra。远程 embedding 模式可把安装参数改为 `-e . --group dev`。

`.env` 填写生成 key；根目录 `.env.local` 仅由启动脚本加载。手动运行时先导出配置，或把相关值放在 `server/.env`。外部进程环境变量优先于 dotenv。配置与模块单例在启动时读取，修改后重启。

## 目录

```text
src/
├─ main.py          # FastAPI 应用、中间件、启动恢复、静态前端
├─ api/             # health/auth/docs/ingest/ask/conversations/agents/metrics/alerts
├─ auth/            # 演示账号、JWT、角色依赖
├─ core/            # 解析/切块/向量/检索/生成/离线评测
├─ graph/           # 客服图、RAG 图、mock 示例
├─ tools/           # 演示订单/物流
├─ services/        # 客服服务、RAG 融合、存储与可靠性
├─ observability.py # trace_id 与日志
└─ cli.py           # CLI 模块入口
```

`data/docs/` 是演示素材，`data/uploads/` 是上传落盘，`data/_parse_cache/` 是解析缓存，`qdrant_data/` 是默认本地向量库。测试位于 `tests/`。

## 配置索引

| 配置 | 默认/含义 |
| --- | --- |
| `SERVER_HOME` | 缺省为当前目录；正常从 `server/` 启动 |
| `DEEPSEEK_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 生成 key / `https://api.deepseek.com` / `deepseek-v4-flash`（代码默认值） |
| `EMBED_BASE_URL` / `EMBED_API_KEY` / `EMBED_MODEL` | 不配地址则本地；key 可复用 `SILICONFLOW_API_KEY`；默认 `BAAI/bge-large-en-v1.5`，维度固定 1024 |
| `MINERU_TOKEN` | 可选；SDK 云解析，失败降级 |
| `SILICONFLOW_API_KEY` / `RERANK_SCORE_THRESHOLD` | 有 key 才精排；默认过滤阈值 0.3 |
| `QDRANT_URL` / `QDRANT_API_KEY` | 缺省 local；配置后走远端 |
| `QDRANT_QUANTIZATION` | 可选 `int8`，仅新建集合生效 |
| `MYSQL_HOST/PORT/USER/PASSWORD` | 可选 MySQL，默认端口 3306 |
| `MYSQL_DB` + `MYSQL_DATABASE` | 两者都配置且相同，分别供会话/文档/checkpoint 与指标/告警使用 |
| `AUTH_JWT_SECRET` / `AUTH_TOKEN_TTL_HOURS` | 演示签名密钥 / 默认 24 小时 |
| `AUTH_OPERATOR_*` / `AUTH_CUSTOMER_*` / `AUTH_OPERATORS` | 默认账号覆盖 / 额外坐席 JSON |
| `LLM_CLASSIFIER` | 默认关闭，设 `1` 启用 LLM 意图分类 |
| `RATE_LIMIT_ENABLED` / `RATE_LIMIT_PER_MINUTE` | 默认开启，客服消息 POST 每 IP 每 60 秒 30 次 |
| `CIRCUIT_FAILURE_THRESHOLD` / `CIRCUIT_COOLDOWN_SECONDS` | 订单熔断默认 5 次失败 / 30 秒冷却 |
| `REDACTOR_ENABLED` / `REDACTOR_MASK_CHAR` / `REDACTOR_RULES` | 默认开启、`*`；自定义规则格式见 `services/redactor.py` |
| `ALERT_HANDOFF_RATE/ERROR_RATE/UNFOUNDED_RATE` | 默认 0.5 / 0.3 / 0.3；命中条件是大于等于 |
| `ALERT_MIN_SAMPLES` / `ALERT_WEBHOOK_URL` | 默认 10；可选告警 webhook |
| `LOG_LEVEL` | 默认 INFO |

生成模型名只是仓库配置默认值，不代表外部供应商可用性已经验证。配置模板见 [server/.env.example](.env.example) 和 [根目录 .env.local.example](../.env.local.example)。

## CLI 与验证

```bash
.venv/bin/python -m src.cli --help
.venv/bin/python -m src.cli cs-eval --fail-under 0.9
.venv/bin/python -m src.cli cs-redteam --fail-under 0.9
.venv/bin/python -m src.graph.quickstart_example '什么是混合检索？'

# 使用真实向量库/模型；与 local API 服务串行运行
.venv/bin/python -m src.cli ingest data/docs
.venv/bin/python -m src.cli ask '什么是 AI Agent？'
.venv/bin/python -m src.cli eval
```

pytest 已配置 `pythonpath=.`，仓库根测试入口则将 `server/` 加入搜索路径。直接从 `server/` 执行 `python -m src.cli` / `uvicorn src.main:app` 可以加载源码；从其它目录运行或使用 `server-cli` 命令时先完成 editable 安装。旧目录迁移后请重新执行安装命令，不继续使用旧 editable 路径。

## 部署与数据边界

根目录 Dockerfile 安装 `pip install ./server`，不包含 `[local]`，必须配置远程 embedding。静态资源由 FastAPI 挂载 `web/dist`，默认端口 80。local Qdrant 单目录单进程，API 与 CLI 不得同时使用同一个目录。

会话存储的 `storage` 可为 `mysql`、`memory` 或 `memory_fallback`；回退内存不迁移原 MySQL 历史，重启会丢失内存数据。文档表 `rag_documents` 由文档存储读写，当前没有自动创建/迁移实现；部署前按实际 SQL 准备表（见 [架构文档](../docs/architecture.md)）。

API 的鉴权、监控限制与本次验证范围见 [API 文档](../docs/api.md) 和 [校准记录](../docs/documentation-audit.md)。本次未连接生产数据库或外部模型做端到端验证。
