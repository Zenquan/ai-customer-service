# 坐席分配：当前实现与后续计划

> 校准日期：2026-10-14。原方案的多坐席、领取/释放、基础自动指派与前端分栏已经实现；在线状态、超时回池、技能组尚未实现。

## 已采用的设计

| 能力 | 当前行为 |
| --- | --- |
| 账号来源 | 默认演示 operator + `AUTH_OPERATORS` 注入额外坐席，复用 `AuthUser` |
| 会话归属 | `assignee_id` / `assignee_name` / `assigned_at`，MySQL 与内存双实现 |
| 领取 | `handoff/manual` 会话可领取；存储 CAS 仅空归属成功 |
| 释放 | 仅当前归属坐席可释放，清空三字段，状态不变 |
| 自动指派 | 转人工回复持久化后，在全量 operator 中选已分配会话数最少者 |
| 回复身份 | 当前登录坐席 ID/展示名，客户端 `agent_name` 不再采信 |
| 页面 | 「全部 / 我的 / 待分配」、领取按钮、归属名、当前登录坐席名 |
| 审计 | claimed/released/manual_reply 事件含坐席 ID；审计存储有内存降级 |

无需为该实现创建独立 `agents` 或心跳表。坐席名称保存在会话和审计中，消息行本身没有专用经办人字段；人工回复响应携带名称和 ID。

## 配置多坐席

在后端启动环境中设置，或在启动脚本读取的根 `.env.local` 中追加（下面是 shell/dotenv 格式）：

```bash
AUTH_OPERATORS='[{"id":"op2","username":"bob","password":"replace-with-strong-password","display_name":"Bob"}]'
```

缺省只有默认 operator；数组解析失败被忽略，无账号/密码的项跳过，ID 与默认用户冲突时跳过。修改后重启后端。账号仍是启动时加载的演示数据，不具备在线账号管理或密码重置。

## 存储与 API

`conversations` 自动建表并对老表幂等补列：

```text
assignee_id   VARCHAR(64) NULL
assignee_name VARCHAR(64) NULL
assigned_at   DATETIME NULL
```

MySQL 领取 `UPDATE ... WHERE assignee_id IS NULL`，根据受影响行数判定成功；内存用进程锁保护。存量空归属且处于 `handoff/manual` 的会话出现在待分配列表。

以下端点都要求 `operator` Bearer token，路径均相对 `/api/v1`：

| 端点 | 语义 |
| --- | --- |
| `GET /conversations?filter=all\|mine\|unassigned&limit=50` | mine 取登录坐席 ID；没有客户端 `agent_id` 过滤参数 |
| `POST /conversations/{id}/claim` | 空请求体；成功返回 claimed 与归属；冲突/状态不符 409 |
| `POST /conversations/{id}/release` | 空请求体；本人可释放，失败 409 |
| `POST /conversations/{id}/messages/manual` | `{message}`；人工状态且归属允许才回复 |
| `GET /agents` | ID、用户名、展示名、已分配会话计数 |

领取与释放不等于关闭会话；当前没有 closed 状态、结束接口或自动回到 AI。页面已封装 release API，但未提供释放按钮。请求示例见 [API 文档](api.md)。

## 自动指派的实际口径

服务层 `_auto_assign` 读取最近最多 1000 条会话，按 `assignee_id` 累计数量，选择最少的 operator；平局取账号遍历顺序靠前者。计数包含所读取范围内所有已分配会话，未只过滤 `handoff/manual`，也不代表坐席在线在办量。`GET /agents` 的 `active_count` 使用同样的截断计数。

不检查登录会话、心跳、技能或响应超时。默认单坐席通常立即获得转人工会话，待分配池可能为空；没有可用坐席或自动指派失败时保留空归属。

## 已知差距

- 人工回复对已归属他人的会话做拒绝，但未分配会话自动认领的 CAS 失败返回值没有检查；并发领取后仍继续回复的竞争路径需要修复。
- 自动指派计算与写入不是跨会话事务，多个并发转人工可能同时选择同一坐席；CAS 仅保证单会话归属写入。
- 会话列表先取最近 500 条再过滤，默认返回 50；我的/待分配可能遗漏更早会话，尚无分页契约。
- 没有在线/离线状态、超时重分配、技能组、工单生命周期或精确负载 SQL。
- MySQL 失败回退内存，归属/审计无法跨进程持久化，也没有自动迁移历史。

## 后续迭代与验收

| 优先级 | 工作 | 验收 |
| --- | --- | --- |
| P0 | 人工回复 CAS 失败后停止并校验归属 | 竞争领取/回复中失败者不落回复、不冒认身份 |
| P1 | 分页、精确负载、人工状态过滤与释放入口 | 老会话可查，计数口径一致，释放后进入待分配 |
| P1 | 在线状态、超时回池、关闭会话 | 只给可用坐席分配，未响应会话可回收 |
| P2 | 技能组路由、工单对接 | 意图匹配技能组，可追溯交接与处理人 |

已存在 `test_agent_assignment.py` 与存储/人工回复测试，本次全量后端通过；单元测试通过不证明上述并发和生产 SQL 边界已解决。验证范围见 [校准记录](documentation-audit.md)。
