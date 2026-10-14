# web · 智应客服中心前端

> 校准日期：2026-10-14。当前提供登录、运营工作台和客户聊天窗，客服主链路使用 SSE。

## 页面与技术栈

`App.tsx` 根据登录角色渲染：未登录显示 `LoginPage`；`customer` 显示 `CustomerChat`；`operator` 显示会话侧栏、对话主区与实时上下文。知识库管理、告警和性能看板通过弹窗打开。

依赖范围见 `package.json`：React 19.2、TypeScript 6.0、Vite 8.2、antd 6.6、`@ant-design/x` / `x-sdk` / `x-markdown` 2.9。安装版本以 `pnpm-lock.yaml` 为准。

```text
src/
├─ main.tsx                 # StrictMode + App
├─ App.tsx                  # 双角色页面、侧栏刷新、功能弹窗
├─ lib/
│  ├─ auth.ts               # 演示 token/用户缓存（localStorage + 内存）
│  ├─ api.ts                # JSON 类型与请求，自动携带 Bearer token
│  └─ chat-provider.ts      # 客服 SSE Provider + 兼容 ragProvider
└─ components/
   ├─ LoginPage.tsx / CustomerChat.tsx
   ├─ ConversationSidebar.tsx # 全部/我的/待分配、领取、归属展示
   ├─ ChatPanel.tsx           # useXChat、人工回复、消息轮询
   ├─ ContextPanel.tsx        # 当前链路、检索依据
   ├─ AnswerView.tsx          # Markdown、引用徽标与来源卡片
   ├─ KnowledgePanel.tsx      # 上传/统计/列表/删除
   ├─ AlertsPanel.tsx
   └─ MetricsPanel.tsx
```

## 数据流

`createCustomerServiceProvider(conversationId)` 请求 `POST /api/v1/conversations/{id}/messages/stream`，创建时读取当前 token 放入 Authorization。`transformParams` 只提交 `{message}`，用户身份由后端 token 解析。

| SSE 事件 | Provider 行为 |
| --- | --- |
| `progress` | 显示处理阶段，不拼进正文 |
| `materials` | 保存检索素材 |
| `token` | 把 `text` 增量拼接到当前回答 |
| `meta` | 设置完整业务/澄清/转人工回答与路由状态 |
| `done` | 更新回答、引用和校验结果 |
| `error` | 保存错误，呈现失败状态 |

`ragProvider` 仍保留，用于兼容 `/api/v1/ask` 的非流式 JSON；主工作台与客户聊天窗使用客服 SSE Provider。完整协议见 [API 文档](../docs/api.md)。

`useXChat` 管理请求状态与消息，`Bubble.List` 使用 `role` 配置与 `contentRender` 自定义渲染。人工回复调用 `api.sendManualReply`，身份取服务端登录坐席；客户端不再提交 `agent_name`。客户和工作台轮询消息，侧栏也定时刷新。列表数据来自后端，不依赖 `useXConversations` 的本地状态。

领取按钮与会话筛选已经实现；释放 API 客户端已封装，当前页面没有释放按钮。额外坐席需配置后端 `AUTH_OPERATORS`，不能只在前端添加用户。

## 开发与构建

从 `web/` 执行，先确保 Node 和 pnpm 均在 PATH（Docker/CI 使用 Node 22、pnpm 11.7.0）：

```bash
pnpm install --frozen-lockfile
pnpm dev          # 默认 :5173，代理 /api → http://127.0.0.1:8000
pnpm lint         # oxlint
pnpm build        # tsc -b && vite build，产物 dist/
pnpm preview      # 默认 :4173，仅用于静态产物预览
```

`pnpm-workspace.yaml` 位于 `web/`，强制 `highlight.js: 10.7.0`，与传递依赖的语言文件导入匹配。修改依赖或 override 后才使用 `pnpm install --no-frozen-lockfile` 更新锁文件，提交前重新构建。

Vite 只有 `server.proxy`，没有 `preview.proxy`。preview 的相对 `/api` 请求不会自动发往 :8000，后端允许 :4173 的 CORS 也不能代替代理。联调使用 `pnpm dev`；单容器部署由 FastAPI 同域托管前端。后端改端口时需同步 `vite.config.ts`，前端改端口时核对后端 CORS。

## 当前限制与验证

登录态存于 localStorage，没有令牌刷新或服务端注销；这属于演示认证。页面顶部「系统在线」文案是静态展示，不能作为模型、数据库或工具健康的证据。

来源徽标只反映序号校验；不能把「校验通过」等同答案事实无误。SSE 不经过 JSON 响应脱敏中间件，输出保护范围以实际服务链路为准。

本次 lint/build 与接口验证结果见 [校准记录](../docs/documentation-audit.md)。页面交互、移动端布局和线上连接须另外做浏览器验证。
