硬性纪律：读 ops/agent-improvement-workflow.md（含外部 PR 对账）；改行为同步改测试写 WHY、门禁全绿才提交；commit footer Claude-Session: https://claude.ai/code/session_01MCgbwMrTqp7jKcDnSVm4zT；收尾 issue comment+换标签 stage:已实现待复测+dispatch done。
⚠️bench（各 repo 主目录 bench-verify 分支）正被用户手测：绝不碰主目录、绝不重启服务、绝不 reset/写 DB（agent/lab DB 都在 talos-postgres:5433）。你的全部工作在指定 worktree。
任务：实现 c12-ai/BIC-meta #25 方向(a)（bench/demo 数据）：Mind mock（med005_fixture / mock 客户端）为 demo 分子（Sonogashira：C#CC(C)(O)C.BrC1=CC=C(I)C(COC)=C1>>...）补真实解析行——真实反应物名称/SMILES/角色，替换 Acetic acid/Ethylamine stub；structure_url/rendered_rxn_url 不再指向不可达 minio.local（用可达占位或本地 minio 资源）。
worktree：git -C /Users/wenlongwang/Work/BIC/talos/BIC-agent-service worktree add /Users/wenlongwang/Work/BIC/talos/.wt/be-25 -b fix/issue-25-demo-fixture fix/chat-ux-lang-error-tubeid。
先 gh issue view 25 --repo c12-ai/BIC-meta --comments（S2 已定位 stub 生成点）。方向(b)（产品显式降级）不做，comment 注明留 Drake。Refs c12-ai/BIC-meta#25。不 push。
