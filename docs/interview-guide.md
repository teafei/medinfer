# 项目讲解与技术检查指南

## 一分钟介绍

MedInfer 是我围绕医疗文本科研需求构建的个人推理与评测工具。它把 MLX、Ollama、vLLM 的流式输出映射到统一接口，用 FastAPI 提供 OpenAI chat 兼容子集，并在固定合成病例上记录性能、任务输出和评分。已经在 Apple M5 上真实运行 DeepSeek-R1-Distill 1.5B 四位量化模型；Ollama/vLLM 的协议测试与部署路径已经准备，云端 GPU 性能没有冒充实测。

项目采用 AI 辅助开发。面试前应能独立解释、运行和修改以下关键路径；不要把生成代码本身包装成手写推理引擎或底层模型创新。

## 可以直接查看的证据

- `medinfer/backends/base.py`：为什么统一的是流式事件而不只是一个 `generate()` 字符串。
- `medinfer/backends/http.py`：Ollama 的 NDJSON 与 vLLM 的 SSE、终止标记、独立 usage chunk。
- `medinfer/backends/mlx.py`：为何模型和 Metal 状态由一个专用线程拥有；并发请求会排队，不能宣称持续批处理。
- `medinfer/backends/reasoning.py`：思考标签可能跨 token 分块，且开标签可能已经在模板里。截断思考不能算摘要答案。
- `medinfer/benchmark/engine.py`：单调时钟、首个非空输出、warmup、信号量、失败和中断状态。
- `medinfer/benchmark/scoring.py`：未知与阴性分开；严格匹配的局限；摘要指标为何叫代理指标。
- `evidence/*.json`：原始输出、模型快照、数据哈希、参数、每个请求的指标，足以重新计算摘要统计。
- `tests/`：SDK、协议、超时清理、并发、持久化和评分边界，而非只验证 HTTP 200。

## 应当能回答的问题

| 问题 | 回答重点 |
|---|---|
| 相对直接使用 Ollama 增加了什么？ | 共同测量/评分协议、跨后端事件模型、原始证据与 SQLite 历史；底层推理仍复用成熟运行时 |
| TTFT 到底从哪里计时？ | 从 benchmark 请求进入观察器到第一个非空文本或 reasoning chunk；不把空 role chunk 当 token |
| TPS 是不是 GPU 解码速度？ | 这里是客户端可观察速率，含 reasoning/provider token 定义和尾部处理；整轮 token 吞吐另算，不与纯 kernel 吞吐混写 |
| 为什么并发 4 没有保证更快？ | 本地 MLX 串行执行，并发增加后端排队；vLLM 批处理需要另行在 GPU 验证 |
| 为什么不把 RSS 当显存？ | RSS 是本进程内存；MLX Metal 峰值是分配器指标；远端 GPU 显存无法由本机 RSS 推断 |
| QA 得分低说明什么？ | 小模型、严格最短答案格式、生成参数与数据规模共同影响；必须看原始答案，不能等同于医学知识准确率 |
| 摘要没有 forbidden phrase 是不是无幻觉？ | 不是；该指标只检索预设短语，存在漏检与误报，不支持临床安全结论 |
| 如何进行公平比较？ | 固定数据/提示、token 预算、温度、缓存与warmup策略，记录硬件/量化/版本，重复独立实验，报告错误与截断 |
| 下一步最有价值的工作？ | 小预算跑一次 7B vLLM 的真实 c1/4/8/16 对照；先补证据再考虑更大模型或功能 |

## 现场演示

1. 启动本机 MLX 网关，展示模型快照和已有真实 run。
2. 打开逐请求记录，选择一个抽取错误或 length 截断案例，解释评分与失败含义。
3. 展示 OpenAI SDK 的真实流式调用与 usage。
4. 修改并发参数，解释 MLX 串行队列，不把 c4 叫 GPU 并行。
5. 查看测试与 CI 配置，区分本机通过、远端 CI 尚未运行、GPU 未验证。

## 不写进已完成成果的内容

未运行的 NVIDIA 部署、32B 性能、吞吐提升百分比、大规模分布式推理、DeepInfer 后端、临床有效性/安全性以及生产级医疗合规。模型生成的医学文字只作为评测输出。项目的可信度来自可复现证据和清楚的工程边界。
