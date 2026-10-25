# 简历项目表述

以下描述对应当前本机交付，需在你亲自复现并理解代码后使用。AI 辅助开发可如实说明，不要求声称全部代码独立手写。云端未实跑的部分用“实现适配/提供部署路径”，不能写成“已部署并验证”。

**MedInfer｜医疗文本大模型私有化推理与评测工具**
Python / FastAPI / MLX / Ollama / vLLM API / SQLite / pytest / Docker

- 构建统一流式 Backend Interface 与 FastAPI OpenAI-compatible chat API，适配 MLX、Ollama、vLLM 协议；在 Apple Silicon 本机运行 DeepSeek-R1-Distill 1.5B 四位量化模型。
- 设计覆盖信息抽取、文本问答、病历摘要的 36 项合成任务，区分未知/阴性与思考/最终答案，记录 TTFT、P50/P95 延迟、token 吞吐、截断及资源范围，保留逐请求原始证据。
- 实现 SQLite 结果持久化、Web 可视化与 JSON/CSV 导出，通过 Python 3.11–3.13 测试矩阵与 Docker 远端 CI；完成本机并发 1/4 实测及干净环境安装复现。

若版面只允许两条，可保留前两条，并在第一条末尾补“配套可视化、持久化与自动化测试”。不建议把单次小模型吞吐数字放在主简历里；硬件、token预算、量化和样本数会占用大量解释空间。详细结果与质量失败保留在 GitHub，技术面试时可追溯。

完成真实 vLLM 实验以后，才可补充“在 [实际GPU] 上部署 [实际模型/量化]，完成固定 workload 下 c1/4/8/16 对照”。性能提升须绑定相同任务、预算、硬件和错误率，写出基准条件。当前不填写这条。
