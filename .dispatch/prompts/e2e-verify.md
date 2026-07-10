# E2E 独立验收轮（S-verifier，author≠verifier）

你是独立验收员。先读 /Users/wenlongwang/Work/BIC/talos/.claude/agents/bic-e2e-runner.md。台架全真（BE @ ca19223 已含全部今晚修复）。允许 reset（轮开始一次）。方法学同 #134/#141：BE 契约+wire+Mind 捕获为主证据。

## 复测清单（每项二元 PASS/FAIL，引用原 issue 验收锚点）
1. #129：TLC 三轮全败→accept→恰一条后续消息（数 text_done），无"问下一步"。
2. #130：同链 live 不刷新监控横幅非红（读事件断言）。
3. #136：真 Mind goal-confirm 后 REST 确认→非基准行入库 amount/eq 为空。
4. #103：确认后 reactant name 保留（草稿名或 chem 名）。
5. #126：CC 推荐不追问溶媒/比例（只问粗产物质量）。
6. #117/#108：重试环每轮有叙述、下发话术无"待处理/排队"。
7. #113：FP 空上游诚实降级不编造不追问。
通过项把对应 issue 标签 已实现待复测 → 已验证（若无该标签则建 stage:已验证）；不通过项评论证据并转 待修复。
## 收尾
汇总报告 → 新建 issue「独立验收轮 1 报告」；dispatch done（FACTS/Judgment 分开）。
