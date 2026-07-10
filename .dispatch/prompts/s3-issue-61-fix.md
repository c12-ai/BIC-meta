# S3 任务：实施 c12-ai/BIC-meta#61 修复 — available_of_type 排除废弃箱（用户已翻案：修）

你是 S3（实现 + 提交）。调查已完成（issue #61 评论 4921386377 详版）：根因与方案都已定点，直接按它实施。

## 已定的修复方案（前 S3 调查结论，你复核后照做或给出更优）
- 单点：lab `app/tlc/inventory.py::available_of_type`（inventory.py:82）排除 disposal bin（`TLC_BEFORE_CC_DISPOSAL_BIN_SLOT`）实例，兑现其 docstring 自称的 "Non-disposed" 语义。
- 该谓词同时喂分配 `_first_available` 与就绪 `count_available`——一处改，派发与预检同时痊愈（预检不再把废弃板算作在库=假绿灯消失）。
- 只排 disposal bin 不动 waste bin；不造库存行（PRD rule 6）；不绕 #32 校验。

## 工作区
- `git -C /Users/wenlongwang/Work/BIC/talos/BIC-lab-service worktree add -b fix/issue-61-plate-fallback /Users/wenlongwang/Work/BIC/talos/.wt/lab-61b origin/main`（lab bench 现在直接跑 main）。
- 不碰 bench 主目录、不重启（root 合入时统一重启 lab）、不 push、不开 PR。

## 二元验收（issue #61 三条照抄，写成测试）
1. _001 在 disposal bin 且架上有可用板 → 新 TLC 派发选可用板成功（注入库存状态的集成测试）；
2. 无可用板 → 错误分型=耗尽，文案与行为一致（"supply-shelf fallback"文案分支要么可达要么删除）；
3. 连续两轮不 reset、第二轮 TLC 可派发；
4. 就绪计数不再把废弃板算在库（预检假绿灯测试）。
全量 lab pytest 绿 + ruff/pyright 干净。

## 收尾
修复摘要（sha、测试计数）评论 issue #61，标签改 stage:已实现待复测；dispatch done。完成后 root 立即合入重启（用户在等这个修复）。
