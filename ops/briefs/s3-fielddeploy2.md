# S3 任务：现场（orin-tail）例行更新到各仓 main 最新 — 用 make field-* 走全流程

你是 S3（现场滚更操作员，列车口径）。工具与权威文档：`make field-dry` / `make field-update`（包 `ops/field/update.sh`）+ `ops/field/README.md`。**现场访问一律 `ssh orin-tail`（tailscale）。**

## 背景（2026-07-13 已知状态，先核实再信）

- 上次滚更后现场：BE=804fba5、portal=field-f44310a、lab=e5cab37、chem=bfff9ab（CI-only 落后可忽略）、mock=d8d63ac；
- **已知押后项**：portal main 的 item-card 重构（#74，`4915908`）依赖 **BE#126（reconcile-and-validate 端点）与 lab#119（atomic relocate）**——上次检查时两者未合。
- mock 已适配 following-phase（d8d63ac），mock 先于 lab 是安全方向。

## 步骤

1. `make field-dry` 看盘点与守卫输出；
2. **依赖核实**：`gh pr view 126 --repo c12-ai/BIC-agent-service --json state` 与 `gh pr view 119 --repo c12-ai/BIC-lab-service --json state`；
   - 两者均 MERGED → BE+lab+portal 三件套同批滚（先 BE/lab 后 portal，portal 依赖后端端点在场）；
   - 任一未合 → **portal 保持押后**（如 update.sh 盘点到 portal 落后，用 `--only` 排除 portal，只滚已就绪的仓）；把押后事实评论到 portal PR#74 的依赖链或 meta 台账；
3. 兼容判断：若 lab 有 runtime 变更（following-phase 合入 main 与否），核对 mock（d8d63ac 已带 TLC_OBSERVATION/TLC_ADDITIONAL_ROUND handler + shared-types 1.4.0）后以 `FLAGS='--ack-compat'` 确认；若 lab 引入 mock 未知的新技能类型，**停手报告**，勿滚 lab；
4. `make field-update FLAGS='...'` 执行；若 update.sh 自身出 bug，修它（meta 仓，分支→PR→admin merge→重跑）——脚本也是本次交付物的一部分；
5. 滚更后验证（update.sh 内置之外补两项）：`make field-status` 五服务 healthy；若滚了 lab/BE，`rabbitmqctl list_queues name consumers` 消费者归位；若滚了 portal，实测登录页可达 + bundle 无 localhost:18080（脚本已断言）+ **给 Wenlong 留一句：item-card 新交互上线，物料面操作方式变了**；
6. 新增 env knob 处理：若 compose/.env.example 有新 key（如 TLC_DEVELOP_WAIT_SECONDS），现场 .env 定值并在报告里注明取值依据。

## 二元验收

- 滚更后现场每个已滚服务的容器 revision 标签 == 对应仓 origin/main sha（portal 用 tag）；
- 五服务 healthy + 上述补充验证全过；
- 报告（评论到 meta 台账 issue #279 或新评论）：各仓 旧sha→新sha、押后项及理由、env 取值、验证证据。

## 纪律

- 现场只做本任务范围的写操作（compose pull/up、.env 追加 key）；绝不动共享基建/bic-sa-*/bic-*-v1；不跑 lab reset；
- done 用单行短摘要+核退出码，长版落台账评论。
