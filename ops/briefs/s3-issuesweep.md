# S3 任务：issue 三态清理（c12-ai 全仓 open issues 台账清扫）

你是 issue 清扫会话（只动 issue 元数据与评论，不写代码）。

## 范围

`c12-ai/BIC-meta`、`BIC-agent-service`、`BIC-agent-portal`、`BIC-lab-service`、`mars_interface_mock`、`BIC-infra`、`BIC-shared-types` 的全部 OPEN issues。

## 三态处置（逐个判定，证据链走 squash 内容核验法：issue 号在 merge 正文 + 具名测试在 main，勿用 SHA 祖先）

1. **已验证 → 关闭**：修复已合 main 且有客观验证（具名测试/CI/一手复测记录）且不属"用户报告待用户目验"类——关闭并评论证据链接。
2. **已实现待复测 → 标注**：修复合了但终验权在用户（台架目验类）——确保 stage 标签/评论最新（PR sha + 复测步骤一句话），**不关闭**；汇总成一份"用户复测清单"（issue 号 + 一行复测动作）。
3. **真 open → 留言现状**：无修复的，评论当前状态（等外部/排队中/需设计），过时描述纠正。外部依赖类（#127 rt=0.0 确认、#163 等 Mind 内网发版、lab#81 多烧瓶）标注等待对象。

## 特别项

- meta#153/#152 若仍开且验收已在评论留痕 → 属状态1。
- c177 留的两处 FP-split 文档 FLAG（anm-handbook§4、lab-logistics-validation.md:21）：确认是否已有 issue 跟踪，没有就开一个（属后续 review 阶段的输入）。
- 不要关闭任何你无法给出一手证据链接的 issue——宁可留在状态2/3。

## 交付

- 每仓处置统计（关闭 n / 待复测 n / 留言 n）+ 用户复测清单，评论到一个新开的 meta 台账 issue（标题：issue 台账清扫 2026-07-11）。dispatch done（FACTS/JUDGMENT 分开）。
