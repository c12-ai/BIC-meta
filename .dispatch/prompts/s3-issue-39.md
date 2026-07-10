你是 S3 评审+实现角色。读 ops/agent-improvement-workflow.md。⚠️bench 主目录（bench-verify）用户手测中：只读主目录、勿重启、勿写 DB（5433）。工作区 /Users/wenlongwang/Work/BIC/talos/.wt/narrate（refactor/narrate-contract）。
任务：修 c12-ai/BIC-meta #39（P1 回归，先 gh issue view 39）。
根因排查主线（差分法）：fix 分支 57ae857 上 #8 seed 工作（T-verify 证据）；bench-verify（fix+narrate+state 合并）上冷表单 rxn=null。头号嫌疑你分支的 f65c36a（transition-turn form drop 处理）；用 git diff 57ae857..refactor/narrate-contract -- 相关文件 + 复现（写小驱动或单元级集成测试穿 reception→subgraph rehydrate→cold emit 全链）定位丢 seed 的环节。
修两件事：1) seed 恢复（回归修复 + 一个穿透全链的集成测试防再回归——现有单测只测了 reception 与 emit 两段，中间断层没覆盖，这正是回归漏网原因，Rule 7 写明 WHY）；2) 过渡模板按契约吃状态：只在 draft.rxn 非空时用"已预填"文案，否则用如实变体。
修好后在 refactor/narrate-contract 上 commit（Refs c12-ai/BIC-meta#39，footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT），然后 dispatch ask 请示 root 是否立即把修复合入 bench-verify 并重启（用户在测，重启要 root 协调）。收尾 comment+标签+dispatch done。
