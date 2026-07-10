硬性纪律：读 ops/agent-improvement-workflow.md（含外部 PR 对账）；改行为同步改测试写 WHY、门禁全绿才提交；commit footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 issue comment+换标签 stage:已实现待复测+dispatch done。
⚠️bench（各 repo 主目录 bench-verify 分支）正被用户手测：绝不碰主目录、绝不重启服务、绝不 reset/写 DB（agent/lab DB 都在 talos-postgres:5433）。你的全部工作在指定 worktree。
任务：实现 c12-ai/BIC-meta #32（用户拍板：做）——lab /preparations/validate 对 TLC 也跑 _validate_tlc_objects，消除 dry-run 与 create-gate 判定分叉；顺带核实并修"检查就绪"假绿灯（若同源）。
worktree：git -C /Users/wenlongwang/Work/BIC/talos/BIC-lab-service worktree add /Users/wenlongwang/Work/BIC/talos/.wt/lab-32 -b fix/issue-32-validate-tlc fix/chat-ux-lang-error-tubeid，工作在其中。
先 gh issue view 32 19 --repo c12-ai/BIC-meta --comments（#19 的 S3 复核有精确 file:line：command_validator.py:687-692 故意跳过、_hydrate_for_materials :797-800 downgrade）。契约行为变更按 Rule 10 同步 lab spec；commit 注明待 Drake 复核；Refs c12-ai/BIC-meta#32。不 push。
