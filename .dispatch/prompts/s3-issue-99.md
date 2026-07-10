# S3 任务：c12-ai/BIC-meta#99 — mock 机器人上传真实板照（方案A）

你是 S3（独立复核 + 实现 + 提交）。issue #99 正文是任务书。仓：/Users/wenlongwang/Work/BIC/talos/mars_interface_mock（本地 mock，直接在其上开侧分支 feat/issue-99-plate-upload；先 git status 确认工作区干净、有未提交内容先评论请示）。

## 要点
- 夹具在 assets/tlc_plate_fixture.png（已就位）。上传实现用轻量 S3 客户端（该仓依赖最小化——minio 或 boto3 择一，看 uv 依赖现状）；env 配置 endpoint/bucket/keys（默认本地 localhost:9000 兼容旧行为，台架另配 150）。
- 拍照类步骤（tlc_mock_interface.py 两处 images 构造）上传后报真实键；存储不可达 fail-loud。
- 完工后不重启（root 统一配置 env→150 并重启 mock）。

## 二元验收
issue #99 四条照抄执行（端到端条留待 root 配合 #98 复测，注明）。仓内自测/lint 绿。

## 收尾
修复摘要（sha、测试）评论 issue #99，标签改 stage:已实现待复测；dispatch done（FACTS/Judgment 分开）。
