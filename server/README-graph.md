# LangGraph 编排层

> 校准日期：2026-10-14。代码已合并到 `src/graph/`，仓库没有独立 `langgraph/` 子项目或 `langgraph.json`。

## 客服图与服务层路由

客服图的节点与分支：

```text
START → load_session → classify_intent
  ├─ knowledge_question → retrieve → compose_answer → validate_answer
  │                                      ↑                 │
  │                                      └─ 引用不合法重写 ─┤
  │                                          合法 → finalize → END
  │                                  重写仍不合法 → handoff → END
  ├─ greeting / unknown / 低置信度追问 → clarify → END
  ├─ after_sale / complaint → handoff → END
  └─ order_query → extract_slots
       ├─ 缺单号 → clarify → END
       └─ execute_order_tool
            ├─ ok → finalize → END
            ├─ not_found 首次 → clarify → END
            └─ not_found 连续两次 / forbidden / timeout / error → handoff → END
```

引用校验失败按 `MAX_REWRITES=2` 计数，达到上限转人工；不要把该常量直接解读为保证执行两次额外生成。

同步客服 API 优先通过客服图处理；流式 API 在服务层做三层路由：显性业务与订单澄清续轮走图，其余知识问题走 `services.rag.ask_stream`。无素材第一次追问，下一轮仍无解转人工；人工状态客户新消息仅入队。流式知识链路尚未整体迁入图。

坐席通过人工回复接口处理 `handoff/manual` 会话，身份取当前 `operator`。转人工后服务层尝试自动指派；归属、领取、释放与并发限制见 [坐席文档](../docs/agent-assignment-plan.md)。

## 目录和契约

```text
src/graph/
├─ customer_service/
│  ├─ state.py          # CustomerServiceState
│  ├─ classifier.py     # 规则、多意图、注入检测
│  ├─ llm_classifier.py # 可选 LLM 分类器
│  ├─ adapters.py       # 延迟导入 RAG Core
│  ├─ nodes.py          # 客服图节点
│  ├─ graph.py          # 构图、条件边、订单熔断包装
│  └─ agent.py          # 同步/异步 ask、thread_id 与 get_state
├─ state/ / nodes/ / graph/ / agent/  # 兼容 RAG 图
└─ quickstart_example.py             # mock 示例
```

客服 retriever：`(query, top_k=5) -> list[dict]`；generator：`(question, contexts, history) -> (answer, citations)`；分类器输出 `intent`、`intent_confidence`、`slots`，可附多意图与澄清信息。

默认适配器调用 `src.core.retrieve.retrieve` 和 `src.core.generate.generate`，不导入外部 `rag` 包。当前 RAG generator 适配器接受 `history` 但不传给核心生成函数；checkpoint 保存历史不代表 LLM 已使用全部历史。

规则分类器默认开启；`LLM_CLASSIFIER=1` 时服务层尝试 LLM 分类，低置信度（<0.7）可追问，无 key、非法输出或调用失败回退规则。多意图按投诉 > 售后 > 订单 > 问候仲裁，规则层命中提示注入后标记 `security_flag`。规则与红队基线不能证明所有注入变体都被阻断。

## Checkpoint

服务层创建 Agent 时调用 `build_checkpointer()`：MySQL 配置有效时使用 `MysqlCheckpointSaver`，否则内存 checkpointer。MySQL 表为 `langgraph_checkpoints` / `langgraph_checkpoint_writes`，`thread_id=conversation_id`。

`messages` 使用 `add_messages` 累加，订单意图与槽位作为续轮信号；`load_session` 重置每轮输出。知识无素材澄清计数另存 `graph_checkpoints`，与 LangGraph 原生表不是同一机制。直接创建 Agent 未传 checkpointer 时不会保存跨轮状态。

## 使用示例

以下 shell 命令从 `server/` 执行，先按 [后端 README](README.md) 安装：

```bash
.venv/bin/python -m src.graph.quickstart_example '什么是混合检索？'
.venv/bin/python -m pytest tests/test_graph_customer_service.py tests/test_checkpoint_resume.py tests/test_citation_rewrite.py tests/test_graph_rag.py
```

无需外部模型的客服示例（Python）：

```python
from src.graph.customer_service import create_customer_service_agent

agent = create_customer_service_agent(
    retriever=lambda query, top_k=5: [{"doc": "demo.md", "seq": 0, "text": "本项目使用混合检索。"}],
    generator=lambda question, contexts, history: ("本项目使用混合检索。[来源1]", [1]),
)
result = agent.ask("什么是混合检索？", conversation_id="demo-1", user_id="demo-user")
print(result["final_answer"])
```

兼容 RAG 图：`START → retrieve → rerank → generate → validate → finalize → END`，非法引用可回到 generate；该图测试/示例使用 `[1]` 格式，客服与产品主链路使用 `[来源1]`。不要把兼容格式作为产品 API 的新约定。

没有配置 LangGraph Studio 启动文件或 CLI 依赖，因此不能直接按旧文档运行 `langgraph dev`。需要 Studio 时另行准备配置并验证。
