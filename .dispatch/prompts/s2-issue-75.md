# S2 任务：查证 c12-ai/BIC-meta#75 — 样品柱双写入口的行为差异与依赖

你是 S2（只读查证，不改代码，结论评论到 issue #75）。issue 正文含两问（行为差异、隐藏依赖）。

## 纪律
- 只读 portal/BE 代码（bench 主目录只读）；DB 只读。不改代码、不重启。
- 查证后评论 issue（Facts/Judgment 分开）：两入口的枚举源、写入字段、覆盖时序、e2e/测试依赖清单；给收敛方案的改动量估计。标签 stage:待调查 → stage:已析根因。dispatch done。
