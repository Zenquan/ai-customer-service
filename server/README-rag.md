# RAG Core · 解析、检索与可溯源生成

> 校准日期：2026-10-14。核心代码位于 `src/server/core/`；安装依赖与配置见 [后端 README](README.md)。

## 链路

```text
资料 → 解析 → 清洗 → 结构感知切块 → 本地/远程 embedding → Qdrant
问题 → 向量 + 标题加权 BM25 → RRF → 可选 rerank → 编号资料 → LLM → 引用范围校验
```

`CHUNK_SIZE=800` 是同章节完整段落的聚合目标，不是字符硬上限；默认 overlap 为 0。切块保存 `chapter/title/section/heading_path/para_range`，章节上下文进入 embedding 与生成 Prompt。

| 参数 | 代码默认值 |
| --- | --- |
| Embedding 模型 / 维度 | `BAAI/bge-large-en-v1.5` / 固定 1024 |
| 集合 | `rag_minimal` |
| `TOP_K` / `RERANK_TOP_K` | 5 / 3 |
| 候选倍数 / RRF k | 4 / 60 |
| BM25 k1 / b | 1.2 / 0.75 |
| Rerank 模型 / 过滤阈值 | `BAAI/bge-reranker-v2-m3` / 0.3 |
| LLM 模型 | `deepseek-v4-flash`（配置默认名） |
| LLM timeout / SDK retries | 60 秒 / 2 |

上述值从 `core/config.py` 读取，不代表外部服务或模型已验证可用。rerank 默认请求开启，无 key 跳过，调用失败回退融合结果。

## CLI

以下命令从 `server/` 执行，先完成 editable 安装；使用 Qdrant local 时停止 API 服务并串行执行：

```bash
.venv/bin/python -m server.cli ingest data/docs
.venv/bin/python -m server.cli ask '什么是 AI Agent？'
.venv/bin/python -m server.cli ask '什么是 RAG？' --no-rerank --top-k 8
.venv/bin/python -m server.cli run data/docs '什么是混合检索？'
.venv/bin/python -m server.cli eval
.venv/bin/python -m server.cli eval --rerank --ks 1 3 5
.venv/bin/python -m server.cli doc-list
.venv/bin/python -m server.cli doc-delete '01-AI-Agent入门.md'
```

目录入库递归收集白名单文件，文档名保留相对路径；单文件与上传 API 使用 basename。CLI 的核心入库/删除不操作 MySQL 文档备份，生产文档管理使用 API 或服务层。

可编程调用：

```python
from server.core.main import ask, ingest, run

stats = ingest("data/docs")
answer = ask("什么是 AI Agent？")
result = run("data/docs", "什么是混合检索？")
```

需要文档 MySQL 备份时使用 `from server.services import rag`，再调用 `rag.ingest_dir("data/docs")`，或上传 API。备份失败会降级；文档表需要预先准备。

## 解析、存储与引用

TXT/MD/MARKDOWN 直接读取；其它格式优先 MinerU 云 SDK，失败尝试 markitdown 与文本兜底。云解析按文件内容 SHA-256 缓存于 `data/_parse_cache/`。降级成功不保证 PDF/图片的语义解析质量，应检查文本后再入库。

Qdrant 默认 local，配置 `QDRANT_URL` 与可选 `QDRANT_API_KEY` 后切远端。point ID 由 `sha256(doc_name + ':' + seq)` 前 8 字节计算并截取低 63 位，跨进程稳定；不是 Python `hash()`。同名文档重入库 upsert 并移除过期序号，上传同名文件会覆盖落盘文件，不提供文档版本历史。

换 embedding 模型或维度需要重建匹配的索引；当前维度 1024 固定在代码中。`QDRANT_QUANTIZATION=int8` 仅新集合生效，其实际内存和召回收益需测量。

产品引用使用 `[来源N]`，校验只验证序号在 `1..素材数` 范围内；没有引用也可能通过范围校验。它无法证明引用文字支持结论。`/ask` 返回校验结果，客服图可按不合法引用重写；流式 RAG 最终发送校验结果，不具备同样的整图重写保证。

空库/无素材：核心 `ask` 返回 `error`；服务层 `/ask` 转为友好提示并清除该业务错误；流式客服资料不足进入澄清/转人工。请按调用层区分错误语义。

## 离线评测

`eval` 使用 `data/eval_cases.json`，支持相关 chunk 或文档标注，输出 Recall@K / MRR。`cs-eval` 使用客服任务标注集，mock 工具跑图；`--with-retrieval` 才接真实索引并计算检索指标。

目前仓库仅包含两份 Markdown 演示资料，标注集还引用额外 PDF；必须先提供匹配资料再解释检索结果。本次未跑真实检索评测，不能沿用旧文档的 Recall/MRR=1.0 作为当前结果。

切块实验入口是 `python -m server.core.exp_chunk_size`，它逐轮删除当前集合并重建。仅在隔离实验数据根或实验 Qdrant 上运行，禁止直接用于业务索引。本次未执行该实验。

## 常见问题

- `ModuleNotFoundError: server`：在 `server/` 完成 editable 安装；测试配置的 pythonpath 不会自动作用于 CLI。
- Qdrant `AlreadyLocked`：停止其它使用同目录的 API/CLI 进程，或使用远端 Qdrant。
- 修好解析器后答案仍含乱码：检查索引中的旧 chunk，针对受影响文档删除后重新入库；不用默认清空整库。
- 模型下载失败：检查网络和缓存；代码默认设置 `HF_ENDPOINT` 与禁用 XET，可通过环境覆盖。默认模型不是旧文档写的 bge-small-zh。
- `from mineru import MinerU` 失败：本仓库使用 `mineru-open-sdk==0.2.5`，与其它 MinerU 包的接口不能混用。
- 文档源文件已更新但问答不变：已入库内容不会自动跟随磁盘变化，重新入库后验证检索。
