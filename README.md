<p align="center">
  <img src="logo.png" width="150" alt="智应客服中心 logo" />
</p>

<h1 align="center">ai-customer-service · AI 智能客服产品</h1>

文档知识库、可溯源问答、LangGraph 客服编排与人工坐席工作台。后端使用 FastAPI，前端使用 React、TypeScript 和 Ant Design X。

> 校准日期：2026-10-14。能力描述以当前仓库代码为准；本次验证结果见 [文档校准记录](docs/documentation-audit.md)。当前仍包含演示账号和演示订单源。

## 产品能力

| 模块 | 当前实现 | 页面入口 |
| --- | --- | --- |
| 知识库 | 上传 PDF/TXT/MD/MARKDOWN/DOCX/HTML/JPG/PNG，列表、切块统计、单文档删除 | 工作台「知识库管理」弹窗 |
| 知识问答 | 结构感知切块、向量与标题加权 BM25 双路召回、RRF、可选 rerank、来源引用 | 运营对话主区 / 客户聊天窗 |
| 客服路由 | 投诉/售后/订单/问候分流；知识问题检索优先；资料不足追问，连续无解转人工 | 气泡链路标签 / 右侧上下文 |
| 订单工具 | 演示订单/物流只读查询，参数与归属检查，缺单号澄清；查无此单先追问，连续两次失败转人工 | 客服图工具节点 |
| 双端登录 | 演示 JWT，`operator` / `customer` 两种角色 | 登录页 |
| 人工接管 | 客户人工会话只入队；坐席回复以登录身份记录，双端轮询同步 | 工作台人工回复区 |
| 坐席分配 | 多坐席账号、领取/释放、转人工自动指派、会话归属字段 | 侧栏「全部 / 我的 / 待分配」 |
| 存储 | 会话/消息与 checkpoint 可使用 MySQL，失败回退内存；文档切块可同步 MySQL用于空索引恢复 | API `storage` / 服务日志 |
| 可靠性 | 解析降级、解析缓存、LLM 超时重试、订单熔断、消息限流、审计与脱敏 | 后端服务层 |
| 评测 | 客服任务与红队离线门禁、运营性能摘要、Prometheus 和告警配置 | 「性能」/「告警」弹窗 |

引用校验检查的是来源序号范围，不能单独证明答案事实正确。JWT 当前只保护部分接口；知识库和会话读取未实现完整资源权限或租户隔离。监控的 MySQL 聚合限制见 [架构文档](docs/architecture.md)。

## 快速开始

从仓库根目录准备环境（Python 3.12、Node.js 22 或满足前端依赖要求的更新版本、pnpm；Docker/CI 使用 pnpm 11.7.0）：

```bash
# 后端：dev 是依赖组，local 是可选 extra
cd server
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[local]' --group dev
cp .env.example .env
cd ..

# 可选 MySQL / 账号 / 告警配置
cp .env.local.example .env.local

# 前端
cd web
pnpm install --frozen-lockfile
cd ..

# 前后端一起启动（:8000 + :5173）
./scripts/start.sh
```

编辑 `server/.env`，填写 `DEEPSEEK_API_KEY`；`MINERU_TOKEN` 和 `SILICONFLOW_API_KEY` 按解析/精排需要配置。本地不配 `EMBED_BASE_URL` 时需要 `[local]` 的 FastEmbed；使用远程向量服务时可安装 `-e . --group dev`，配置远程地址、模型和 key。当前向量维度固定为 1024，模型须匹配。

MySQL 配置同时设置 `MYSQL_DB` 和 `MYSQL_DATABASE` 为同一个数据库名：会话/文档/checkpoint 读取前者，指标/告警读取后者。根目录 `.env.local` 由 `scripts/start.sh` 加载；手动启动不会自动读取它。

手动启动的两个终端均从仓库根目录开始：

```bash
# 终端 1：先导出根目录配置，再切到 server/
set -a
source .env.local
set +a
cd server
.venv/bin/python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000 --workers 1
```

```bash
# 终端 2
cd web
pnpm dev
```

打开 `http://localhost:5173`，登录后上传资料并提问。接口文档在 `http://127.0.0.1:8000/docs`。

| 角色 | 演示账号 | 默认密码 | 用户 ID |
| --- | --- | --- | --- |
| 运营 | `zenquan` | `zenquan123` | `zenquan` |
| 客户 | `alice` | `alice123` | `demo-user` |

可通过 `AUTH_*` 环境变量覆盖密码和账号。`AUTH_OPERATORS` 注入额外坐席，详见 [坐席分配文档](docs/agent-assignment-plan.md)。修改配置后重启后端。

演示订单 `A00001` 属于 `demo-user`，Alice 登录后可查；`B00001` 属于 `alice` 这个用户 ID，和登录名为 Alice 的 `demo-user` 不同，用于验证越权拒绝。

启动脚本允许 `BACKEND_PORT` / `FRONTEND_PORT` 覆盖端口，但 Vite 代理固定指向 `127.0.0.1:8000`，CORS 也只列出 5173/4173；改端口时须同步修改对应配置。`pnpm preview` 没有开发代理，要联调请使用开发服务器或同域容器。

## Python 与依赖约束

`.python-version` 和 Docker 使用 Python 3.12；两个 `pyproject.toml` 声明的兼容范围实际是 `>=3.10,<3.13`。项目统一用 3.12 开发与验证。本地 FastEmbed/ONNX Runtime 的历史兼容问题是选择该版本的原因，不据此断言所有新版本和平台都不支持。

后端依赖的唯一声明位置是 `server/pyproject.toml`，`langgraph>=0.2.60,<1.0`、`langchain-core>=0.3.0,<0.4.0`；`local` extra 安装 FastEmbed，`dev` 依赖组安装 pytest。仓库没有跟踪 `uv.lock`，安装结果受依赖范围与包源影响。

## 架构与目录

后端源码直接位于 `server/src/`，使用 `src.*` 导入；应用入口为 `src.main:app`，CLI 入口为 `python -m src.cli`。发行包名称仍为 `server`。迁移后重新执行 editable 安装，以更新虚拟环境的源码路径。

```text
web/ React + Ant Design X
  ├─ lib/api.ts：JSON API + Bearer token
  └─ lib/chat-provider.ts：客服 SSE / 兼容非流式 ask
                ↓ /api/v1（开发经 Vite 代理）
server/src/
  ├─ main.py：路由、中间件、lifespan、静态前端
  ├─ api/：HTTP 契约、登录与坐席角色依赖
  ├─ auth/：演示账号、JWT、角色解析
  ├─ services/：客服路由、RAG 融合、存储、指标/告警/可靠性
  ├─ graph/：客服图 + 兼容 RAG 图
  ├─ tools/：演示订单/物流只读工具
  ├─ core/：解析、切块、向量、检索、生成、引用校验
  └─ cli.py：python -m src.cli
```

运行数据默认以 `server/` 为根：`data/uploads/`、`data/_parse_cache/`、`qdrant_data/`；可通过 `SERVER_HOME` 指定根目录。必须从 `server/` 启动或设置正确的 `SERVER_HOME`。Qdrant local 同一目录只允许一个进程：API 服务与 CLI 不能同时占用本地索引。

入库：上传 → 解析（MinerU / markitdown / 文本降级）→ 清洗与结构切块 → 向量化 → Qdrant → 可选 MySQL 文档备份。

问答：问题向量与 BM25 → RRF → 可选精排/阈值过滤 → 编号素材 → LLM → 引用范围校验。同步客服通常走图；流式客服的知识分支由服务层直接调用 RAG，业务与澄清分支走客服图。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [server/README.md](server/README.md) | 后端安装、配置、测试与部署 |
| [server/README-rag.md](server/README-rag.md) | RAG API、CLI、默认参数与数据边界 |
| [server/README-graph.md](server/README-graph.md) | 图结构、依赖注入、checkpoint 与引用约定 |
| [web/README.md](web/README.md) | 双端页面、SSE Provider、开发与构建 |
| [docs/architecture.md](docs/architecture.md) | 分层、数据模型、存储与可靠性边界 |
| [docs/api.md](docs/api.md) | 全部业务端点、鉴权、错误、SSE 与 curl 示例 |
| [docs/agent-assignment-plan.md](docs/agent-assignment-plan.md) | 已实现坐席分配与剩余工作 |
| [docs/customer-service-plan.md](docs/customer-service-plan.md) | 当前能力、后续规划与验收标准 |
| [docs/documentation-audit.md](docs/documentation-audit.md) | 本次文档范围、验证结果和已知差距 |

`server/data/docs/` 的两份 Markdown 是知识库演示素材，更新文件不会自动更新已入库向量。

## 测试、评测与诊断

```bash
# 从仓库根目录：全量后端测试
server/.venv/bin/python -m pytest

# 以下从 server/ 执行（完成 editable 安装后）
cd server
.venv/bin/python -m src.cli --help
.venv/bin/python -m src.cli cs-eval --fail-under 0.9
.venv/bin/python -m src.cli cs-redteam --fail-under 0.9
.venv/bin/python -m src.cli cs-eval --json
.venv/bin/python -m src.graph.quickstart_example '什么是混合检索？'
```

真实检索评测与文档操作也从 `server/` 执行，先停止占用本地索引的 API 服务：

```bash
.venv/bin/python -m src.cli ingest data/docs
.venv/bin/python -m src.cli ask '什么是 AI Agent？'
.venv/bin/python -m src.cli eval
.venv/bin/python -m src.cli cs-eval --with-retrieval
.venv/bin/python -m src.cli doc-list
```

CLI 的 `ingest` 走 `src.core.main`，不会同步 MySQL 文档备份；需要备份时使用上传 API 或服务层 `rag.ingest_dir`。

前端验证从 `web/` 执行：`pnpm lint`、`pnpm build`。CI 当前执行客服/红队门禁、选定的后端测试和前端应用类型检查，并未覆盖后端全部测试、前端 lint/build。

每个请求响应携带 `X-Request-ID`，业务日志输出 stdout 并带 trace_id；无请求场景显示 `-`。默认 `LOG_LEVEL=INFO`。指标出口：`/metrics`（Prometheus）与 `/api/v1/metrics/summary`（运营 JSON）；配置在 `deploy/prometheus/` 与 `deploy/grafana/`。JSON 摘要支持 MySQL，Prometheus 与应用内告警目前依赖内存事件，详见架构文档。

## 单容器部署

根目录 `Dockerfile` 在镜像内构建前端，运行阶段安装 `server` 包并托管 `web/dist`；Python 3.12、默认 `PORT=80`、单 worker、健康检查 `/api/v1/health`。密钥与 MySQL/向量服务配置由平台环境变量注入。

容器不安装 FastEmbed，须配置 `EMBED_BASE_URL` 与有效 key；MySQL 文档备份成功且 Qdrant 集合为空时，启动会尝试恢复索引。恢复失败只记日志，不能据此承诺重部署永不丢数据。外部 Qdrant 用 `QDRANT_URL` / `QDRANT_API_KEY` 配置，切远端本身不保证其它组件适合多 worker。

CloudBase 的分支绑定、自动部署和线上状态由平台控制台决定，仓库无法证明它们已启用；本次未部署。

## 后续迭代

已具备客服 MVP、演示认证、评测与基础坐席工作台。下一阶段先补齐资源鉴权、真实业务源、监控聚合、坐席并发边界与生产账号体系，再推进受控写操作、工单和在线坐席路由。详细状态见 [规划文档](docs/customer-service-plan.md)。
