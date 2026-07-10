# 重构任务 B：Lab 校验单一流水线（create / dry-run / readiness 共用一个校验核）

你是重构 session（独立设计 + 实现 + 提交）。整体依据：`/Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/project-refactor-review-2026-07-09.md` §B（先读）。

## 工作区纪律（必须遵守）
- 自建 worktree + 分支，基于 lab fix 分支的当前 tip（含 #32 的 f2c80fe）：`git -C /Users/wenlongwang/Work/BIC/talos/BIC-lab-service worktree add -b refactor/lab-validation-pipeline /Users/wenlongwang/Work/BIC/talos/.wt/lab-validation <lab fix 分支名>`（先 `git branch -a` 确认分支名，f2c80fe 所在分支）。
- **绝不**触碰 bench 主目录工作区（lab 服务在跑、用户手测中），绝不重启服务、不写 DB、不 push、不开 PR。

## 病灶（台账证据）
- #32 根因：create-gate（task_service.py:114-121，TLC 先 validate_tlc_task_params 再 validate_task_materials）与 dry-run（preparations.py:186，只调 validate_task_materials）是两条手写路径 → TLC 摆位校验在 dry-run 零覆盖 → 幽灵盒"检查就绪"通过、真派发才炸。
- #32 修复 f2c80fe 把 TLC 补进 dry-run——止血正确，但形态是"按执行器逐个补"＝继续镜像。CC/RE/FP 的同款分叉没有系统性保证。
- #19：错误分型分叉（"不存在"报成"非2ml"，command_validator.py:598 一带）。
- 用户裁定（对 BE 同病）："每一步处理流程应该是一样的，不要镜像，统一流程，各步只注入步骤信息"——同一原则适用于 lab 校验。

## 目标形态
1. 一个校验核：per-executor 校验器注册表（TLC/CC/FP/RE 各自注册参数/摆位/物料校验器），核心流水线统一执行顺序与错误分型。
2. 三个调用方（task create gate、/preparations/validate dry-run、readiness）共用该核：**同一任务状态在任何入口得到逐字相同的 verdict 与错误分型**。
3. f2c80fe 的 TLC dry-run 行为重构为注册表消费者（行为保持，其新增测试作对照）。
4. 错误分型单一来源：对象不存在 / 类型不符 / 数量不足 / 摆位非法各自有稳定错误类型，调用方不再自行改写。
5. 范围控制：不改校验语义本身（哪些规则、何时通过），只收敛路径与分型；语义变更如确有必要，先在 issue 评论列出并 dispatch ask。

## 二元验收（PASS 当且仅当全部成立）
1. 参数化性质测试：对同一 task/库存状态，create-gate 与 dry-run 的校验结果（通过/失败 + 错误类型集合）完全一致；覆盖 TLC/CC/FP/RE 四执行器 ×（缺料 / 幽灵对象 / 类型不符）三类故障注入。
2. 既有 lab 测试全绿（含 #32 的新测试，作为行为保真对照）。
3. 校验核为单一实现：create/dry-run 无重复的校验编排代码（可 grep 断言的结构事实，写进测试或 commit message）。

## 收尾
1. 设计摘要 + commit sha + 测试计数评论到 c12-ai/BIC-meta#32（注明"f2c80fe 的结构化推广"）；若发现 CC/RE/FP 现行 dry-run 确有漏校验的具体实例，逐个开 issue（repo:lab-service 标签）。
2. `dispatch done` 汇报：FACTS 与 Judgment 分开。合入窗口由 root 统一协调。
