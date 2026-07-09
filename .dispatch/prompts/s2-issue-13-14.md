你是 Agent 改进工作流的 S2 调查角色。开工前完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s2-investigate/SKILL.md
铁律：只读调查 —— 不改产品代码、不重启服务、不 reset/写 DB、不跑写库测试（用户正在 bench 测试）。
并发提示：一个 S3 会话正在同一 BE 工作区实现别的 issue —— 若某文件工作区状态疑似编辑中，以 git 已提交状态为准（git show HEAD:<path>），并在 comment 里注明基准 commit。
关键事实：agent DB = talos-postgres:5433 的 talos_agent_db（bic-postgres:5432 同名库是假的）；代码 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid。
产出：根因分析 comment 到 issue（## 根因(证据链 file:line+DB) / ## 根源方案 / ## 影响面与风险 / ## 备选），换标签 stage:待调查→stage:已析根因，然后 dispatch done。

任务（P2 攒批，两个 issue 分别 comment + 换标签）：
1) issue #13：叙述第三人称「化学家」称呼用户本人。评估与 #10 共享语言常量机制合并的可行性（一个共享叙述常量同时管语言跟随+第二人称语态；注意 s3-issue-10 稍后会实现 #10，你的方案要写成可直接并入其实现的形状）。
2) issue #14：objective 思考决策震荡。对三个候选根因定权重（parse_reaction tool_result 信息贫乏 / 缺主反应物→substrate 推断规则 / 谨慎vs行动指令冲突），方案按根因权重给：比如 parse_reaction 返回带每行 SMILES+角色的摘要、objective prompt 加 baseline 推断规则等。铁证：session 8ef85e9d seq544 工具返回只有角色名列表。
先 gh issue view 13 / 14 --repo c12-ai/BIC-meta --comments。
