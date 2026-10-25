# 发布状态

公开仓库：[teafei/medinfer](https://github.com/teafei/medinfer)，可见性为 **Public**。

该版本通过已登录的 GitHub 网页按目录上传，包含源码、原创合成数据、双语文档、真实 MLX 评测记录、截图和 CI 工作流。虚拟环境、模型权重、本地 SQLite 和密钥不进入仓库。GitHub 连接器的写入接口在发布时返回 403，因此使用网页完成发布。

已确认 [首次成功的远端检查](https://github.com/teafei/medinfer/actions/runs/40207616589)：Python 3.11 / 3.12 / 3.13 三组均为 37 项测试通过，Docker 构建、启动和鉴权模型接口检查通过。最新结果以 [Actions](https://github.com/teafei/medinfer/actions) 为准。云端 NVIDIA/vLLM 与临床能力仍保持未验证状态。

获取和体验项目：

```bash
git clone https://github.com/teafei/medinfer.git
cd medinfer
uv sync --locked --extra dev
uv run medinfer --backend mock serve
```

后续修改正常提交并推送，不重复创建同名仓库，也不强制覆盖远端。本地保留发布前的 Git 历史与源码包。
