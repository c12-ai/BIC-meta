# S3 任务：meta 仓三个带 reviewRequests 的 PR 补审 — #169 / #100 / #4

你是 S3（PR 审查会话，列车口径）。背景：meta#209 列车只圈了三个业务仓，meta 仓三个**带 review request** 的 PR 漏审（Wenlong 2026-07-11 指示补上：『排会话审meta』）。

仓：c12-ai/BIC-meta。**合并纪律**：这三个都有 reviewRequests → 审净 ∧ CI 绿即可 admin squash-merge；审出缺陷则评论作者不合并。均为 docs/skill 类 PR，重点是**与当前 main 的事实漂移**，不只是行文。

## 逐 PR 审查要点

1. **#169（bianchunyang，read-only BIC diff/test/risk 分析 skill，reviewReq=1）**
   - 对照 `.claude/skills/` 现有 skill 与 CLAUDE.md SOP Index：职责是否与现有 prd/bump-version 等冲突或重复；
   - skill 声称 read-only——核对其指令确实无写操作/无 push；
   - 若合：SOP Index 表是否需要同 PR 补一行（缺了算不完整，rule 9）。
2. **#100（yanbowang0605，chem service 本地启动文档，reviewReq=1）**
   - 对照现状：chem 已在 bench :8010 跑、`make up` 链含 chem、端口 canon `ops/port-allocation-2026-07-10.md`——文档若写旧口径（其它端口/独立启动方式）即事实漂移，要求更新或代改（小改可代改后合，说明留痕）；
   - 与 CLAUDE.md Local Dev Infra 段是否重复——重复内容应引用而非复制（DRY）。
3. **#4（yanbowang0605，本地化需求文档，reviewReq=2）**
   - PR 号很老，大概率与现行 PRD/实现（zh+en locale 双语已落地、ELN zh/en 报告已上线）漂移；
   - 判定：内容仍有效→更新后合；已被现实超越→评论建议关闭（不代关）。

## 收尾

- 每 PR：评论 verdict（Facts/Judgment 分开）；合并的做内容核验（PR 号在 squash 正文）；
- meta#209 台账评论补一段『meta 仓补审结果』三行表；
- **meta 仓正在被 root 会话频繁推 brief**——动 main 前 `git pull`，只 squash-merge 自己审的 PR，别动 `ops/briefs/`；
- dispatch done（FACTS/JUDGMENT 分开）。

## 并行知会

- s3-pr2947 在 BIC-agent-portal、s3-eln229 在 BIC-agent-service——不同仓无交集。
