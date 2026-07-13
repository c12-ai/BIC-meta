# S3 任务：lab 权限加固五 PR 联审（Lab Service JWT 验证 + CORS 收紧）

你是 S3（PR 联审会话）。**输出纪律：review 意见一律不发到 PR/issue 上**——全文写入本仓 `.dispatch/findings/authreview-2026-07-13.md`（新建），并在 dispatch done 里给出路径+要点摘要。Wenlong 要先在 CC 里预览再决定如何反馈作者。GitHub 上只许只读操作（view/diff/checks），零评论零标签零合并。

## 审对象（一条链，按合并顺序）

| 序 | PR | 内容 |
|---|---|---|
| A1 | c12-ai/BIC-infra#7 | keycloak bic-agent-service confidential client |
| A2 | c12-ai/BIC-meta#171 | env-up 幂等 client seed |
| B | c12-ai/BIC-agent-service#97 | BE 调 lab 带 service-account Bearer |
| C | c12-ai/BIC-agent-portal#36 | portal 调 lab 带 Keycloak Bearer |
| D | c12-ai/BIC-lab-service#112 | lab JWT 验证 + CORS 收紧（**最后合，且 Wenlong 本地开闸验证通过才合**） |

## 审查维度（每 PR 独立结论 + 全链整体结论）

1. **陈旧度**：这批 PR 写于 ~7-10，此后各仓 main 大幅前进（BE 至 804fba5、portal 至 f44310a+、meta 大量 ops 变更）——逐个 PR 检查与当前 main 的冲突/语义漂移（BE 的 lab_client 被 #266 改过、portal 的 lab 调用面被 item-card #74 改过——**重点核对 C 与 #74 的交集**）；
2. **开闸时序安全**：A→B→C 合并后、D 未合窗口期，旧 lab 必须容忍带 token 请求（向后兼容）；D 合后未带 token 的调用方全断——盘点还有谁直接调 lab（mock？脚本？e2e？chem？），列出会被 D 打断的清单；
3. **安全实质**：token 获取与缓存（client credentials 流程、过期刷新）、JWT 验证（签名算法钉死、issuer/audience 校验、时钟偏移）、secret 存放（env/compose，不入 git）、CORS allowlist 内容；
4. **双环境部署就绪**：台架（localhost:18080 issuer）与**现场**（192.168.12.150:18080 issuer、portal origin http://192.168.12.150:15173）——D 的 CORS allowlist 和 issuer 配置是否环境可参数化？`ops/field/` 的 compose/.env.example 需要哪些新 key（列清单，不改）；A2 的 seed 与现场 keycloak realm（已导入）如何对齐；
5. **测试**：各 PR 具名测试覆盖（验证通过/拒绝/过期/错 audience；CORS 允许/拒绝）；
6. **Wenlong 开闸验证脚本建议**：给他一份本地验证清单（合 A-C 后、合 D 前在台架跑什么；合 D 后验什么），二元判据。

## 产物

`.dispatch/findings/authreview-2026-07-13.md`：每 PR 一节（verdict: 可合/需改动清单/需 rebase）+ 全链时序表 + 会被 D 打断的调用方清单 + 双环境新增 env key 清单 + 开闸验证清单。dispatch done 单行摘要+核退出码。
