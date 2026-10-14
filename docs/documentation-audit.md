# 文档校准记录

校准日期：2026-10-14；代码基线为当前工作区（起始 HEAD `caaea3b`）。本次更新文档、配置模板和过时入口注释，不修改业务实现、不发布、不连接生产数据库。

## 检查范围

检查原有 41 份跟踪 Markdown：11 份项目/示例文档、27 份 `.agent/skills` 技能与参考文件、3 份 `.learnings` 历史记录。新增本记录后共 42 份。

- 更新根 README、`docs` 下 API/架构/客服规划/坐席方案、三个后端 README、前端 README和两份知识库演示素材，共 11 份项目文档。
- 校验 `.agent` 内文件链接和代码围栏；修复 4 份参考文件的站点相对链接/错误围栏，保留其余上游技术内容，未对 27 份参考的所有外部 API 逐条做版本验证。
- `.learnings` 视为历史记录，本任务不追加或改写学习条目。执行期间工作区另出现 `.learnings/ERRORS.md`、`.learnings/LEARNINGS.md` 和 `web/src/lib/auth.ts` 的目录/缓存键更新，非本任务写入，保留这些并发修改。
- 补 `.env.local.example` 的 `MYSQL_DATABASE` 和额外坐席示例，校准 `server/.env.example` 的 embedding/解析/阈值注释；修正 pytest/Vite/API、启动脚本、Python 依赖声明、Docker/config 与图示例/切块实验的旧说明注释，运行参数与逻辑不变。

## 主要修正

| 旧表述 | 本次校准 |
| --- | --- |
| 独立 app/rag/langgraph 目录、sys.path 注入 | 统一 server 包，正规模块导入 |
| 非流式单问答、左侧固定知识库 | 双角色页面、客服 SSE、会话侧栏、知识库弹窗 |
| 坐席分配待评审 | 已有多坐席/领取/释放/自动指派，补剩余边界 |
| `[local,dev]` 安装 / 旧 CLI 路径 | local extra + dev group，`python -m server.cli` |
| Python 元数据均严格锁 3.12 | 元数据 >=3.10,<3.13，开发/镜像统一 3.12 |
| 默认 bge-small-zh | 实际默认 bge-large-en-v1.5，1024 维 |
| 用 Python hash 生成稳定 point ID | 实际 SHA-256 派生低 63 位 |
| 登录后所有接口鉴权 | 列出实际鉴权端点、匿名路径与资源隔离缺口 |
| 所有 MySQL 表自动准备 | conversations 等自动建表；messages/graph_checkpoints/rag_documents 缺迁移 |
| MySQL 指标/告警完整、滑动窗口 | JSON 摘要支持 SQL；Prometheus/应用告警只读内存累计事件 |
| CI 全量测试/build 全绿 | CI 文件仅运行选定测试、门禁与前端应用类型检查 |
| 检索 Recall/MRR=1.0、生产全部收口 | 移除无本次证据的数字与完成承诺，单列验证结果 |

第三方链接修复按已打开的官方页面核对：[Chat Provider](https://x.ant.design/x-sdks/chat-provider-cn/)、[useXChat](https://x.ant.design/x-sdks/use-x-chat-cn/)、[Common Props](https://x.ant.design/docs/react/common-props/)。旧 A2UI 站点路径本次无法读取，改链到现有本地 API 参考；未声称上游协议是最新版本。

## 本次验证

| 检查 | 结果 |
| --- | --- |
| 后端全量 pytest | 231 passed，1 个依赖弃用警告 |
| 客服任务 `cs-eval --fail-under 0.9` | 门禁通过，57 条；55 条逐题整体通过，2 条转人工期望不一致 |
| 红队 `cs-redteam --fail-under 0.9` | 13/13 通过，安全阻断率 1.0，仅覆盖当前基线样本 |
| mock 图示例 | 模块入口运行成功，回答/引用输出正常 |
| 前端 `pnpm lint` | 退出码 0，5 条 React 规则警告 |
| 前端 `pnpm build` | 类型构建与 Vite 产物通过；Vite 配置未来兼容与大包警告 |
| OpenAPI 对照 | 20 个业务/运维 method+path 均已在 API 文档覆盖，按依赖代码区分必须登录与可选 token |
| Markdown 与示例 | 42 份文档、96 处本地链接/围栏检查通过；3 段项目 Python 示例 AST 与 22 段 shell 示例 bash 语法检查通过；客服图文档 mock 示例执行通过 |
| 差异检查 | `git diff --check` 通过 |

后端测试命令在 `server/` 执行 `.venv/bin/python -m pytest`。现有虚拟环境的 editable 源路径未跟随目录迁移，直接 CLI 曾报 `ModuleNotFoundError: server`；本次门禁/示例用 `PYTHONPATH=src` 验证，文档保留正确 editable 安装步骤，没有宣称现有虚拟环境已修复。

前端验证使用本机 Node 24.19.0、pnpm 11.25.0；首次执行受到镜像连接和 shell 缺 Node PATH 影响，加入已安装 Node 的 bin 路径后通过。未升级依赖或改变锁文件。未复测 CI 的 Node 22 / pnpm 11.7.0 组合。

前端警告涉及 ConversationSidebar 的组件导出、KnowledgePanel/MetricsPanel 的 effect setState、AnswerView 的 refs/effect；构建还提示 vite.config.ts 的 `__dirname` 未来兼容与主包超过 500 KB。本次未修改这些业务代码。

客服任务实测：

| 指标 | 结果 |
| --- | --- |
| intent_accuracy | 1.0 |
| tool_accuracy | 1.0 |
| forbidden_blocked_rate | 1.0 |
| handoff_accuracy | 0.9649122807 |
| slot_completion_rate | 0.9824561404 |
| first_resolution_rate | 0.4561403509 |

0.9 门禁检查前五项，不检查 first_resolution_rate。两条失败问题是「查一下订单 XYZ999999 的物流」「查订单 ORD20260901001 的物流」，标注期待首次 handoff，而当前实现对 not_found 先澄清一次。需要后续统一产品规则与评测标注，本次不修改语料标签以提高分数。

知识库演示 Markdown 已校准，但没有重新入库或修改已有 Qdrant 数据。标注集含未随仓库提供的 PDF，因此本次未运行真实 Recall@K/MRR；旧文档检索数字不能视作当前复现结果。

## 已知实现差距

- 会话/知识库资源鉴权和多租户隔离不完整；SSE 不经过 JSON 响应脱敏中间件。
- MySQL 使用 MYSQL_DB/MYSQL_DATABASE 两套变量；模板要求同库，代码仍未统一。
- messages、graph_checkpoints、rag_documents 没有集中建表/迁移；文档备份、空索引恢复与部分索引修复不能保证成功。
- Prometheus 抓取重置事件游标可能重复累计，且与应用告警均未接 MySQL 事件 SQL 聚合；应用告警没有时间窗口或去重。
- 未分配人工回复的 CAS 失败返回值未检查；自动指派与列表存在计数截断、无在线状态、无超时回池。
- 默认生成适配器未传历史，保存 checkpoint 不等于完整多轮模型记忆。
- 含斜杠文档名与单段 HTTP 删除路由不匹配；CLI 删除也不操作 MySQL 文档备份。

本次未做外部模型/解析/订单系统联调、生产 MySQL 迁移与重启恢复、浏览器双端交互/移动端布局、Docker 构建或线上部署。上述差距已写入架构与规划，文档完成不等于它们已修复。
