# 合并列车总操作员（用户显式授权：建 PR / push / 合并 / 改同事 PR 分支）

你是合并列车操作员。用户裁定（2026-07-10 晨，verbatim）：「你来dispatch session直接按你推荐顺序操作，把我们的fix都放intergration PR3，一次合并掉，然后其他同事的按顺序批次rebase，解决冲突，提交commit到对应branch，合并，最后本地验证没有问题，写一个文档给团队如何起最新代码，这个最优先」。此授权覆盖：推分支、开 PR、合并 PR、向同事 PR 分支提交 rebase/冲突解决 commit。**严格顺序作业，每步 CI 绿再进下一步。**

仓库根：/Users/wenlongwang/Work/BIC/talos/。参考报告：BIC-meta#133（TLC 双 PR）、#135（Phoenix）、#137（Keycloak）——冲突面与解法都已写明，照做。

## 第 ① 步：我方修复批（用户口径 integration PR3）
1. 先合 shared-types：merge c12-ai/BIC-shared-types PR#95（pic_urls 字段，门禁已绿）；记下合并后 main sha。
2. BE + lab 收编 TEMP pin：两仓把 pyproject 的 [tool.uv] override-dependencies 块删除、[tool.uv.sources] 改 pin 合并后 main sha，uv lock+sync，各自 commit（替代 TEMP 语义，commit message 注明收编）。BE 全量单测 + lab pytest 复跑绿。
3. 各仓推 integration 分支并开 PR（约定：分支 integration/bench-2026-07-10；正文按 issue 分组、用 Refs 不用 Closes、结尾 Claude-Session URL；**PR 增行里不得有 Drake 相关内容、不得有任何待审措辞**）：
   - BIC-agent-service：bench-verify（HEAD b5b6c50+）→ PR → CI 绿 → 合并（沿用该仓既有合并方式，此前为 squash）。
   - BIC-agent-portal：bench-verify → 同上。**绝对纪律：tests/helpers.ts 的工作区改动是台架本地适配，严禁入 commit/PR**（先 stash，推完还原）。
   - BIC-lab-service：bench-verify（含 #61/#68/#115 及 TEMP 收编）→ 同上。
   - mars_interface_mock：查有无 remote；有则同样走分支+PR+合并，无 remote 则确保本地 master/main 合入即可并在报告注明。
4. 合并后各仓本地 main 拉取核验（log 首行 sha 记录进报告）。

## 第 ② 步：TLC 双 PR（svc#73 + portal#21）
- 前置：#133 指出 PR 依赖 lab 分支 feat/op_adapt_v3（purity JSONB）——核实：若 #73 运行时需要，先把该 lab 分支 rebase 到新 main、开 PR、CI 绿、合并。
- svc#73：rebase 到新 main（冲突两处轻量，见 #133：aggregator import 并存、tools.py tlc_sample_tubes 改型保留 cc_cartridge_location），push 到 PR 分支，CI 绿，合并。
- portal#21：rebase 到新 main；**MaterialPreparationPanel.tsx 做真三方 reconcile（两侧语义都保留：bench 的 #90/#116/#123 内联就绪态 + PR 的去维护模式/add-mode），不许 #133 门禁临时用的"整取 PR 版"**；translation union；其余机械冲突照 #133。push、CI 绿、合并。合并后跑 portal 全链门禁确认。

## 第 ③ 步：Keycloak（infra#2 → svc#67 + portal#17 原子批）
- 照 #137：infra#2 先合；svc#67 rebase（uv.lock 重生成；pyproject -bcrypt/+pyjwt 与新 main 的 shared-types pin 对齐）+ portal#17 rebase（3 文件轻冲突 + 死 import 清理），补一条 alembic merge heads（#137 预告），两 PR 同批合并。

## 第 ④ 步：Phoenix（svc#44 → portal#9）
- svc#44：2 处 additive 冲突（service.py __init__ 字段并列、contracts.md 段改号 3e）照 #135 解，rebase、push、CI 绿、合并。
- portal#9：finalizeAssistant 语义冲撞按 #135 的定论解——**保留 #110 文本分段（reclaimEmptyAssistant 依赖），把 target_event_id 穿进 finalize，删 PR 引用的已不存在 updateBubbles**；rebase、push、CI 绿、合并。

## 第 ⑤ 步：本地验证（合并后 main）
1. 台架四仓切到合并后 main（BE/lab/portal/mock），uv sync / pnpm i 按需。
2. 依 CLAUDE.md 冷启顺序重启台架（lab→BE→portal→mock；BE 启动命令必须带 unset all_proxy http_proxy https_proxy ALL_PROXY HTTP_PROXY HTTPS_PROXY 前缀；env 保持 Mind 经 127.0.0.1:8011、S3=192.168.12.150:9000/tlc-images、chem 127.0.0.1:8010——chem 服务在 .wt/chem-95 上跑着不用动）。
3. 门禁：BE 全量单测、portal test+build、lab pytest。
4. 冒烟：reset 后 API 驱动走 objective→confirm→TLC 下发一轮（方法学照 #134/#142，证据留 wire/DB）；Keycloak 合并后若登录链变化，核对 portal 是否需要新 env（.env.example diff）并在文档里写清；点赞点踩组件渲染冒烟（有 Phoenix :6006 就顺验上报，起不了注明）。
5. 任何一步红：修复到绿再前进（rebase 引入的问题你就地修并 push 到对应分支）；无法当场修的，回滚该批合并（revert PR）并在报告里 fail-loud，不许带伤前进。

## 第 ⑥ 步：团队文档
写 /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/run-latest-2026-07-10.md（中文，开头结论段）：如何起最新代码——各仓 main、shared-types pin 说明、docker 基建（postgres/rabbitmq/minio/redis + talos-postgres:5433 口径）、冷启顺序与健康检查、必需 env（Mind/MinIO/chem/DashScope 占位不写真 key）、Keycloak 登录新要求（infra#2 组件怎么起）、Phoenix 可选、reset API、常见坑（代理变量必须 unset、curl --noproxy）。commit 到 BIC-meta（可 push）。

## 收尾
汇总报告评论到 BIC-meta 新 issue「合并列车 2026-07-10 报告」：每步 PR 链接/合并 sha/CI 结论/门禁数字/冒烟证据/回滚记录（如有）。dispatch done（FACTS/Judgment 分开）。
