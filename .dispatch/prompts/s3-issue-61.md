# S3 任务：修复 c12-ai/BIC-meta#61 — TLC 派发死绑 silica_plate_001，不回退可用板（P1 链路断）

你是 S3（调查定位 + 独立复核 + 实现 + 提交）。issue #61 正文 + `/Users/wenlongwang/Work/BIC/V2/BIC-meta/.dispatch/findings/t-main-r2/01*.md`（含截图与双会话证据）是任务书。这是当前最高优先缺陷：每轮金链路必复现，挡住所有下游验证。

## 第一步：定位分配点（跨仓调查，只读）
- BE `/Users/wenlongwang/Work/BIC/talos/BIC-agent-service`（TLC 执行项 allocation——工作区常驻件 silica plate 的选 ID 逻辑）与 lab `/Users/wenlongwang/Work/BIC/talos/BIC-lab-service`（编排/校验，#90 choreography）。主目录均只读（服务在跑）。
- DB 只读取证：lab 库 labrun_db（talos-postgres:5433）里 silica_plate 实例的 location/状态行；_001 的 disposal 状态与可用板行。
- 回答：分配在哪层、为何固定 _001（硬编码 id？排序取首？配置表单行？）、"供料架回退"文案出自哪层。结论评论到 issue #61。

## 第二步：修复（落对应仓的侧分支）
- BE 改动落 `git -C .../BIC-agent-service worktree add -b fix/issue-61-plate-fallback .../.wt/be-61 bench-verify`；lab 改动落 `git -C .../BIC-lab-service worktree add -b fix/issue-61-plate-fallback .../.wt/lab-61 <lab 当前 bench 分支 tip>`（先 git branch 确认）。可能只需其一，以调查结论为准。
- 语义：分配从"固定实例"改为"按真实库存选可用实例"（PRD rule 6：选既有 ID、不造行；rule 7 精神：坐标/实例从实际库存解析，不用文档示例值）；无可用板时错误分型=耗尽、文案与行为一致。
- 不放水：不得在分配层造库存行；不得绕过 #32 校验。

## 二元验收（issue #61 三条照抄，写成测试）
含"连续两轮不 reset、第二轮 TLC 可派发"的集成测试（注入 _001 in-disposal + 架上有货的库存状态）。全量对应仓测试绿 + lint 干净。

## 收尾
调查结论 + 修复摘要（sha、测试计数）评论 issue #61，标签 stage:待调查→已实现待复测；dispatch done（FACTS/Judgment 分开）。合入窗口 root 攒批（本缺陷修复后 root 会让测试员补验下游 #40-#45）。
