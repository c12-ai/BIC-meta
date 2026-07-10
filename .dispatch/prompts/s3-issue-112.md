# S3 任务：c12-ai/BIC-meta#112 — mock 机器人 CC 照片上传（#99 方案 A 平移）

你是 S3（独立复核 + 实现 + 提交）。issue #112 正文 + 调查评论（4925549575）+ root 归层评论是任务书。仓：/Users/wenlongwang/Work/BIC/talos/mars_interface_mock，工作区应在 feat/issue-99-plate-upload（98e938b）——确认干净后直接在其上开新分支 feat/issue-112-cc-photos（不 push/不 PR/不重启，root 统一部署）。

## 要点
- 夹具已就位：assets/cc_result_fixture.png（ChemEngine 官方 smoke 用图，主图）+ assets/cc_instrument_fixture.png（真机仪器屏照）。
- 先核对链路读取点：BE tools.py:897-906 从 trials.result 取 pic_urls（#112 调查）；确认 lab-service 从机器人上报的哪个字段透传（对照 TLC images 的透传路径与 CCExperimentData.pic_urls 契约），mock 在对应 CC 技能（大概率 END_CC / 峰收集完成步）上报照片键列表。
- 复用 #99 的上传器（_upload_plate_photo 族）：上传两张、报 `minio/{bucket}/{key}` 形态键（#98 presign 边界约定），存储不可达 fail-loud code=500。
- CC 技能当前走通用 code=1000 分支——只加照片上报所需的最小实现，别把 CC 全技能细节 mock 出来（Rule 2/3）。
- 仓内自测（selfcheck_replay + smoke_test 模式照抄 #99：上传字节回读断言 + fail-loud 断言）。

## 二元验收
(1) CC 结束类技能上报后，配置存储含两键真字节（smoke 回读）；(2) 报键与实际上传一致且带 minio/ 前缀；(3) 存储不可达 fail-loud；(4) selfcheck + smoke 全绿（含 TLC 既有 13 项不回归）。端到端（BE→Mind cc/result 200→FP 预填非空）留 root 台架复测，注明。

## 收尾
修复摘要评论 issue #112，标签 stage:待修复 → stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
