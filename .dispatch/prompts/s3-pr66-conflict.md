硬性纪律：读 ops/agent-improvement-workflow.md（含外部 PR 对账）；改行为同步改测试写 WHY、门禁全绿才提交；commit footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 issue comment+换标签 stage:已实现待复测+dispatch done。
⚠️bench（各 repo 主目录 bench-verify 分支）正被用户手测：绝不碰主目录、绝不重启服务、绝不 reset/写 DB（agent/lab DB 都在 talos-postgres:5433）。你的全部工作在指定 worktree。
任务（用户指令：帮同事解决 PR#66 冲突）：c12-ai/BIC-agent-service PR#66（yanbowang0605，backend locale）与 main 有冲突。
1) git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add /Users/wenlongwang/Work/BIC/talos/.wt/pr66 && cd 进去 gh pr checkout 66；
2) merge origin/main，逐冲突**语义合并**（对方是 locale 穿透 + 语言规则；main 有 #68 的 narrate grounding 等——两者多为并集关系，参照我们 rebase #68 的先例：保双方语义）；
3) 全量单测+ruff+pyright 全绿；
4) **push 到 PR#66 的 head 分支**（用户已授权此外发动作），并在 PR 里 comment 说明冲突解决方式（列每处冲突的合并决策），署名注明来自 Wenlong 侧协助；
5) 若遇语义两难（双方改同一行为且不兼容），不要硬合——dispatch ask 上报。
注意：不要把我们本地 fix/refactor 分支的内容带进去（那些未 push，PR#66 冲突只针对 origin/main）。
