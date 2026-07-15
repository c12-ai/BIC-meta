# S3 任务：service#94 机械 lint/format 修复（直推作者分支）→ CI 绿后合并

你是 S3（协作修缮 + 合并）。背景 = prtrain-misc 联审结论（meta#209 + svc#94 issuecomment-4941741567）：#94（guardrail，**reviewRequests=2 = 本轮唯一合并合格者**）语义无 BLOCKER、27-case 真值表扎实、分支已被代更到 merge-main（0dbd2fc）；唯一卡点 = 其 app/ 自有代码从未跑过 CI 的机械债——ruff 9 errors（tlc.py 3×S101、workflow_action_authorization.py 5×E501+1×ANN401）+ ruff format 2 文件。用户常令"有冲突就帮助更新然后合并"覆盖此类机械修缮。

仓：BIC-agent-service，直接在分支 `feat/guardrail-action-authorization` 上工作（fetch 确认无作者新推进；禁 force-push；修复为独立 commit，message 注明机械性质引 #209）。

## 范围（严格机械，零语义）

- S101（assert in app/）→ 按仓内惯例改显式 raise/条件；E501 断行；ANN401 补类型或按仓内惯例处理；ruff format 2 文件。**不改任何逻辑**——diff 审查自证（语句级等价）。
- 全量本地 pytest 绿（talos-pg-test-73:5455）；ruff check+format app/ 干净；pyright 改动文件 0。
- push → CI 全绿 → **admin merge**（该 PR 有 reviewRequests，符合用户合并纪律）→ 评论 #209 台账更新 + @作者说明机械修复内容。

## 收尾

merge sha 评论 svc#94 与 meta#209；dispatch done（FACTS/JUDGMENT 分开）。
