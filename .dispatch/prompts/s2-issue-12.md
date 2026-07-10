你是 Agent 改进工作流的 S2 调查角色。开工前完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/.claude/skills/s2-investigate/SKILL.md
铁律：只读调查 —— 不改产品代码、不重启服务、不 reset/写 DB、不跑写库测试（用户正在 bench 测试）。
并发提示：一个 S3 会话正在同一 BE 工作区实现别的 issue —— 若某文件工作区状态疑似编辑中，以 git 已提交状态为准（git show HEAD:<path>），并在 comment 里注明基准 commit。
关键事实：agent DB = talos-postgres:5433 的 talos_agent_db（bic-postgres:5432 同名库是假的）；代码 /Users/wenlongwang/Work/BIC/talos/BIC-agent-service @ fix/chat-ux-lang-error-tubeid。
产出：根因分析 comment 到 issue（## 根因(证据链 file:line+DB) / ## 根源方案 / ## 影响面与风险 / ## 备选），换标签 stage:待调查→stage:已析根因，然后 dispatch done。

任务：调查 c12-ai/BIC-meta issue #12（request_clarification 的提问不可达用户）。先 gh issue view 12 --repo c12-ai/BIC-meta --comments。
必须回答的设计问题：该工具的存在必要性论证（相对出口A表单/纯文本），以及根源方案选型 —— (a) 保留文本问答但建立叙述契约（问题原文第一人称直达，narrate 不得转述丢信息）；(b) 升级为结构化事件 kind（FE 渲染问题卡片）；(c) 其他。评估各选项对 L2/L3 事件契约（Rule 10 spec 影响）与 FE 的改动面。
证据入口：session 8ef85e9d seq546-549；tools.py 的 request_clarification 定义与其 narrate 路径；objective.py:195 注释（"question rides ..."）值得追。
