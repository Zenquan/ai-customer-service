# API 参考

> 校准日期：2026-10-14。以下响应是字段示例，不是线上快照；全部端点与权限按当前路由代码核对。

Base URL：`http://127.0.0.1:8000/api/v1`。`/metrics`、`/api-info` 与 FastAPI `/docs`、`/redoc`、`/openapi.json` 位于根路径。开发代理只转发 `/api`，不转发 `/metrics`。

JSON 请求使用 `Content-Type: application/json`；上传使用 multipart；stream 返回 SSE。所有请求由追踪中间件设置 `X-Request-ID`，调用方可传同名头。CORS 默认允许 localhost/127.0.0.1 的 5173/4173；Qdrant local 必须单进程。

## 权限表

| 端点（相对 Base URL，根路径另注明） | 权限 |
| --- | --- |
| `POST /auth/login` | 无需 token |
| `GET /auth/me` | 已登录用户 |
| `GET /health` | 无认证依赖 |
| `GET /docs`、`DELETE /docs/{doc_name}`、`POST /ingest` | 无认证依赖 |
| `POST /ask` | 无认证依赖 |
| `GET /conversations` | operator |
| `GET /conversations/{id}`、`GET /conversations/{id}/messages` | 无认证依赖，未做会话归属检查 |
| `POST /conversations/{id}/messages`、`POST .../messages/stream` | 可匿名；带 Bearer token 时验证 token 并使用用户 ID |
| `POST .../messages/manual`、`POST .../claim`、`POST .../release` | operator；人工回复/释放另检查归属与状态 |
| `GET /agents`、`GET /metrics/summary`、`GET /alerts/recent` | operator |
| 根路径 `GET /metrics`、`GET /api-info` | 无认证依赖 |

当前接口没有完整会话/知识库资源鉴权与多租户隔离。`tenant_id` 是预留值；订单归属校验不覆盖其它资源读取。不得将本表解读为生产权限方案。

## 登录与用户

`POST /auth/login` 接收用户名 1–64 字符、密码 1–128 字符：

```json
{"username":"alice","password":"alice123"}
```

成功返回 `{token, user: {id, username, role, display_name}}`；错误账号/密码返回 401。默认运营 `zenquan/zenquan123`（ID `zenquan`），默认客户 `alice/alice123`（ID `demo-user`），环境变量可覆盖；额外坐席通过 `AUTH_OPERATORS` 注入。

`GET /auth/me` 需要 `Authorization: Bearer <token>`，返回用户四字段。演示 JWT 默认有效 24 小时，无刷新/注销 API。

下面 curl 示例从仓库根目录执行，先保存运营 token：

```bash
BASE=http://127.0.0.1:8000/api/v1
TOKEN=$(curl -fsS "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"zenquan","password":"zenquan123"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -fsS "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"
```

默认账号覆盖后要替换上述登录参数。TOKEN 是演示联调 shell 变量，不要把真实 token 写入仓库。

## GET /health

读取知识库统计与配置，无请求体：

```json
{
  "status":"ok", "docs":2, "chunks":4,
  "embed_model":"BAAI/bge-large-en-v1.5",
  "qdrant_path":"/path/to/server/qdrant_data",
  "collection":"rag_minimal", "rerank":false,
  "llm_model":"deepseek-v4-flash"
}
```

`docs/chunks` 是当前索引统计；`rerank` 表示配置了 SILICONFLOW key，不代表远程精排可用。该端点不检查 MySQL、生成模型和订单服务就绪；异常可能 500，当前没有 `/ready`。

```bash
curl -fsS "$BASE/health"
```

## 知识库

### GET /docs

返回 `[{"doc":"01-AI-Agent入门.md","chunks":1}]`。CLI 递归入库的名称可能含相对子路径，上传 API 名称为 basename。

### DELETE /docs/{doc_name}

删除文档的 Qdrant chunks，尝试删除 MySQL 文档备份并清检索缓存；成功返回 `{deleted, doc}`，向量库没有该文档返回 404。删除不同存储不是一个事务。

```bash
curl -X DELETE "$BASE/docs/01-AI-Agent%E5%85%A5%E9%97%A8.md"
```

单段名称用 `encodeURIComponent` 编码。当前路由是 `{doc_name}`，不是 `{doc_name:path}`；含斜杠的名称即使用 `%2F` 也可能被路由解码后拒绝，不能保证通过该 HTTP 端点删除。此类名称需服务层管理；CLI 删除只改向量库，不同步 MySQL 备份。

### POST /ingest

multipart 字段 `files`，可多文件。扩展名白名单：`.pdf/.txt/.md/.markdown/.docx/.html/.jpg/.png`。取 basename 落盘 `server/data/uploads/`，逐文件解析/切块/向量化；同名覆盖落盘并更新文档向量，无版本历史。

```bash
curl -X POST "$BASE/ingest" -F 'files=@server/data/docs/01-AI-Agent入门.md'
```

```json
{
  "total":2,
  "docs":[{"name":"01-AI-Agent入门.md","chunks":2,"inserted":2}],
  "skipped":[], "errors":[]
}
```

`total` 是本次成功写入向量数，不是全库总数；`skipped` 是解析空结果或入库阶段异常，`errors` 是格式/写文件失败。没有可落盘的支持文件返回 400：`{"detail":{"errors":[{"name":"a.exe","reason":"不支持的格式 ..."}]}}`。部分失败可仍返回 200，必须检查两个数组；返回成功也不证明 MySQL 文档备份成功。

## POST /ask

兼容非流式 RAG 接口：

| 字段 | 类型/默认 | 约束 |
| --- | --- | --- |
| `query` | string，必填 | 1–2000 字符 |
| `use_rerank` | bool/null，null | null 按默认；true 没有 key 仍跳过 |
| `top_k` | int/null，null | 1–50，默认检索 top 5 |
| `rerank_threshold` | float/null，null | >=0，默认配置阈值 0.3 |

```bash
curl -X POST "$BASE/ask" -H 'Content-Type: application/json' \
  -d '{"query":"什么是 AI Agent？","use_rerank":false,"top_k":5}'
```

```json
{
  "query":"什么是 AI Agent？",
  "materials":[{"doc":"01-AI-Agent入门.md","seq":0,"text":"AI Agent 可通过工具执行任务。","score":0.03}],
  "answer":"AI Agent 可通过工具执行任务。[来源1]",
  "citations":[1], "citation_valid":true,
  "material_count":1, "error":null
}
```

素材可带 `chapter/title/section/heading_path/para_range`，`score` 口径取决于召回/融合/精排阶段，不是回答置信度。`citation_valid` 只验证引用序号范围；未引用也可能通过。

核心错误通常通过 200 的 `error` 返回，如检索或生成失败；空库/无相关素材在服务层转为友好 answer 并清 error。未捕获异常返回 500 + detail。直接 `/ask` 不维护客服状态或澄清计数。

## 客服会话

会话响应 `storage` 为 `mysql/memory/memory_fallback`，表示会话存储模式；不代表所有持久化组件健康。未配 MySQL/发生降级时内存数据随重启丢失。

### GET /conversations

仅运营可读。query：`limit=50`、`filter=all|mine|unassigned`；mine 根据 token 的坐席 ID，未暴露客户端 `agent_id`。当前先读取最近最多 500 条再过滤并截取，不是分页 API。未知 filter 按全部处理，limit 未设置正数范围校验。

```bash
curl -fsS "$BASE/conversations?filter=mine&limit=50" -H "Authorization: Bearer $TOKEN"
```

返回数组元素包括：`id/status/handoff_reason/assignee_id/assignee_name/assigned_at/created_at/updated_at/message_count/first_message/storage`。

### GET /conversations/{id}

摘要响应使用 `conversation_id` 而不是列表里的 `id`：

```json
{
  "conversation_id":"demo", "created_at":"2026-10-14T00:00:00+00:00",
  "updated_at":"2026-10-14T00:00:00+00:00", "message_count":0,
  "status":"open", "handoff_reason":null,
  "assignee_id":null, "assignee_name":null, "assigned_at":null,
  "storage":"memory"
}
```

不存在的会话在该请求中懒创建；不是 404。状态为 `open/waiting/handoff/manual`。未实现关闭状态或独立创建/删除会话 API。

### GET /conversations/{id}/messages

返回按存储顺序读取的消息数组，未分页；不存在会话通常是空数组。字段包括 `id/role/content/created_at`，助手消息还可带 `response_mode/citations/materials/handoff_reason/needs_human`。不是每条消息都包含所有字段。

### POST /conversations/{id}/messages

```json
{"message":"帮我查询订单 A00001 的物流","user_id":"demo-user","tenant_id":"demo"}
```

`message` 必填 1–2000 字符；`user_id/tenant_id` 可空，非空为 1–64 字符。token 用户优先于 body `user_id`；匿名默认身份由 `DEMO_USER_ID`（缺省 `demo-user`）决定。登录名 Alice 对应用户 ID `demo-user`，所以可查询 A00001，不能查询属于用户 ID `alice` 的 B00001。

同步响应包含 `conversation_id/message_id/answer/materials/citations/citation_valid/response_mode/needs_human/needs_clarification/handoff_reason/error/storage`；图分支可额外带 `intent/clarify_reason/tool_results/tool_calls`。

- 知识回答为 answer；无素材第一次 clarify，连续无解 handoff。
- 订单缺单号 clarify，下一轮补单号恢复；not_found 第一次 clarify、累计两次 handoff。
- forbidden/timeout/error，以及投诉/售后进入 handoff。
- handoff/manual 状态的新客户消息只入队，返回等待人工提示，不运行 AI。

### POST /conversations/{id}/messages/stream

请求体与同步相同，响应 `text/event-stream`，`Cache-Control: no-cache`、`X-Accel-Buffering: no`。SSE 帧：

```text
event: token
data: {"text":"回答片段"}

```

| event | 数据与语义 |
| --- | --- |
| `progress` | `stage/label`，过程提示 |
| `materials` | `materials`，生成前检索结果 |
| `token` | `text`，正文增量 |
| `meta` | 完整业务/澄清/人工 answer、模式、原因、引用、工具结果等 |
| `done` | 终态；知识分支可含 answer/citations/citation_valid，图分支可仅含 storage |
| `error` | `error`，流中失败；HTTP 已开启时不能改为 500 |

```bash
# 匿名演示：避免用运营账号查客户订单
curl -N -X POST "$BASE/conversations/demo/messages/stream" \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我查询订单 A00001 的物流","user_id":"demo-user"}'
```

客户端需同时处理 meta 正文、token 增量与 done；done 不保证包含完整字段，流异常也不保证补发 done。业务图完整回答由 meta 一次发送，不是逐 token。

## 人工回复与坐席

均需 operator token。转人工后会尝试自动指派，默认单坐席通常直接归属 zenquan；示例使用同一运营账号回复。

### POST /conversations/{id}/messages/manual

`message` 必填 1–4000 字符。`agent_name` 保留兼容（非空 1–64 字符），但身份实际取 token。

```bash
curl -X POST "$BASE/conversations/demo/messages" -H 'Content-Type: application/json' \
  -d '{"message":"转人工","user_id":"demo-user"}'
curl -X POST "$BASE/conversations/demo/messages/manual" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"您好，我是人工客服，正在核实。"}'
```

成功返回 `{conversation_id, message_id, storage, response_mode:"manual", agent_name, assignee_id}`，会话更新 manual。仅 handoff/manual 且归属允许可回复，否则 409；未分配则尝试自动领取，当前 CAS 竞争边界见 [坐席文档](agent-assignment-plan.md)。

### POST /conversations/{id}/claim

空请求体，仅 handoff/manual 会话可领取；成功：

```json
{"conversation_id":"demo","claimed":true,"assignee_id":"zenquan","assignee_name":"Zenquan"}
```

已有归属（包括自己再次领取）或状态不允许返回 409。

### POST /conversations/{id}/release

空请求体，仅归属本人可释放，返回 `{conversation_id, released:true}`，失败 409；清归属而不改变人工状态。

```bash
curl -X POST "$BASE/conversations/demo/release" -H "Authorization: Bearer $TOKEN"
curl -X POST "$BASE/conversations/demo/claim" -H "Authorization: Bearer $TOKEN"
```

### GET /agents

```json
[{"id":"zenquan","username":"zenquan","display_name":"Zenquan","active_count":1}]
```

`active_count` 是最近最多 1000 条中已分配会话数，没有在线状态/结束过滤，不是精确实时在办量。

## 指标与告警

### GET /metrics/summary

仅运营，JSON 字段：`storage/total/resolved/handoff/clarification/errors/tool_success/tool_failure/citation_valid/citation_invalid/latency_avg_ms/latency_p50_ms/latency_p95_ms/by_intent/by_response_mode/by_tool_status`，无时延样本时相关值可 null。支持 MySQL 和内存聚合，不返回所有指标的百分比，需要按正确分母计算。

### GET /alerts/recent

仅运营，默认 `limit=50`，服务端夹在 1–200，倒序数组：`rule/current_value/threshold/window_samples/conversation_id/trace_id/message/created_at`。达到最小样本且比率 >= 阈值触发应用告警；目前读取内存累计事件，不查询 MySQL 评测事件，未做时间窗口/去重。

### 根路径 GET /metrics

Prometheus 文本，前缀 `cs_eval_`，包括 requests/resolved/human_handoff/clarification/tool_calls/citation_valid/errors counters 与 latency_seconds histogram。不是 `/api/v1/metrics`。

```bash
curl -fsS http://127.0.0.1:8000/metrics
curl -fsS "$BASE/metrics/summary" -H "Authorization: Bearer $TOKEN"
curl -fsS "$BASE/alerts/recent?limit=20" -H "Authorization: Bearer $TOKEN"
```

当前 Prometheus 只消费内存事件，并有重复抓取重置游标导致重复累计的边界；不能把已暴露指标等同为生产监控正确。配置与限制见 [架构](architecture.md)。

### 根路径 GET /api-info

返回 `{"name":"RAG 产品","docs":"/docs","api":"/api/v1"}`。根 `/` 在前端产物存在时显示静态页面；没有产物时不保证有首页。

## 错误、限流与脱敏

| HTTP | 当前场景 |
| --- | --- |
| 200 | 成功，也可能通过 error/skipped/errors 表达业务失败 |
| 400 | 上传没有可保存的支持文件 |
| 401 | 登录失败、需要登录或无效/过期 token |
| 403 | 已登录但不是 operator |
| 404 | 删除不存在文档、路由不匹配 |
| 409 | 领取/释放/人工回复状态或归属冲突 |
| 422 | Pydantic 字段/长度/范围校验失败 |
| 429 | 客户消息 POST/stream 每 IP 限流，含 Retry-After |
| 500 | 未捕获异常；流开启后的异常通常用 error 事件 |

`REDACTOR_ENABLED=1` 默认对 `/api/v1/` JSON 递归脱敏（告警路径例外），含错误 JSON；SSE 不经过此响应中间件。来源序号与 PII 正则保护不是事实正确性或完整安全证明。
