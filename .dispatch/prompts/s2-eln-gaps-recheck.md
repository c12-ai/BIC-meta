# S2 任务：核对 BIC-agent-service#63 的 ELN 数据缺口现状（comment 4921384223 逐项）

你是 S2（只读核对，结论回帖到 BIC-agent-service issue #63）。基准：`gh api repos/c12-ai/BIC-agent-service/issues/comments/4921384223 --jq .body`（yanbowang 2026-07-09 03:47Z 的六项"等后端/数据落库"缺口）。

## 今日已落地、可能移动缺口的事实（核对时纳入）
- BE bench-verify 含 #60（TlcEvidence.plate_image_url 承 robot boxed_pic_url，presigned）与 #72（解析富化服务端权威）；真 Mind 已切 52.83.119.132:8010（mixcase 返回逐化合物 predicted_rf）；本地 BIC-chem-service :8010 已接线（分子量）。
- lab bench-verify 含 #61/#68（RE 计时器持久化）修复。

## 逐项核对（每项给：现状=已通/部分通/仍缺 + 一手证据 file:line 或 DB/接口实测）
1. scientist/operator 数据源——sessions/users 表现在有无可反查字段（DB 只读）。
2. CC/UV 图片（pic_urls/annotated_pic_urls）——CC evidence 契约与真 Mind CC 分析响应实测（只读探测 8010 的 openapi + 必要时一次只读调用）有没有图 URL。
3. TLC 斑点形态结论（spot_morphology/tailing）——真 Mind TLC recognition 响应实测有无该类字段。
4. RE rpm——REParam/shared-types 现契约；真 Mind RE recommend 响应有无 rpm。
5. RE 视觉观察结论——Mars/lab RE result（含 #68 修复后）有无文字/状态字段。
6. RE/冷凝管图片 URL——robot mock 的 RE 终报与 lab evidence 有无 image key。

## 纪律
- 全程只读（代码/DB/接口只读探测，不高频）；不碰 bench 主目录、不改代码。
- 结论回帖 BIC-agent-service#63（Facts/Judgment 分开；逐项表格：缺口→现状→证据→建议归属 repo），并 @提及原评论作者口径差异处。
- dispatch done：FACTS=六项各一句话现状；Judgment=哪些缺口今日事实上已被解锁、建议的落库顺序。
