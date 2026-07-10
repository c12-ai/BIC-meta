---
name: env-up
description: 一键起 BIC 本地台架（lab/BE/portal/mock/chem + infra + keycloak）。用 make up / make doctor / make status，不要手抄冷启步骤。触发：用户要起环境、"环境挂了"、"起不来"、doctor 报红、要重启某个服务、冷启后台架体检。
---

# env-up — 用 make 起台架，不要手抄步骤

**核心原则**：所有冷启知识都编码进 `scripts/bic-env/*` 了。你的工作是**跑 make、读 doctor 的可执行输出、按红牌自带的 `→ fix` 命令处置**——不要凭记忆复述冷启顺序，也不要通读 `ops/run-latest`。

从 **meta 仓根目录**跑（本机 repos 在 `/Users/wenlongwang/Work/BIC/talos`，需 `BIC_ROOT` 指过去）：

```bash
BIC_ROOT=/Users/wenlongwang/Work/BIC/talos make doctor   # 先体检（只读，绝不动运行态）
```

## 决策树

1. **先 `make doctor`**（只读，安全，随时可跑）。看 Verdict：
   - `DOCTOR: GREEN` → 台架已起，无需动作。要看一屏概览就 `make status`。
   - `DOCTOR: N RED` → 每张红牌下面有一行 `→ fix: <命令>`。**照抄那条命令执行**即可；能自愈的 `make up` 会自愈。
2. **要（重新）起环境** → `make up`（幂等：已健康的服务自动跳过；不会打断在跑的台架）。
   - 想先看会做什么、不真执行 → `make up DRY=1`（打印计划，零改动）。**在别人正在用台架时先 DRY 看一眼。**
3. **单个服务挂了** → `make restart-<svc>`（`lab|BE|portal|mock|chem`），带同款健康门。
4. **收环境** → `make down`（只停 app 进程，**保留共享 docker infra**——别人还在用）。真要连 infra 一起停：`make down INFRA=1`。

## 读 doctor 输出的要点（都是今晚踩过的真坑）

- **5433 隧道遮蔽**：doctor 若报 `5433 is an ssh TUNNEL`，说明端口被 ssh 隧道占了、apps 会连错库。照红牌 `kill <pid> && docker start talos-postgres`。
- **端口占用分内外**：占用者是我们自己的旧进程 → `make restart-<svc>` 会 kill 重起；**外来进程（DMPK/隧道等）doctor 只红牌不杀**——不动别人的东西，按红牌命令自己判断。
- **portal 假绿**：doctor 查的是 `/src/main.tsx` 返回 JS（真能编译），不是 `:5173` 的 200。报 `white-screen risk` 就是 `pnpm install` 没跑。
- **代理毒化**：doctor 显示 proxy 指向 127.0.0.1:7890 是**已处理**（BE 启动带 `unset`，健康检查用 `--noproxy`）——不是问题。

## 边界

- doctor **只读**，永远可以在被占用的台架上跑。
- `make up` **不 clone 仓库**；缺仓库时 doctor/up 会红牌指向 `make bootstrap`。
- profile 默认 `minimal`（Mind mock + 本地 MinIO）；全真档 `BIC_PROFILE=full-real`（读 .env 现值不覆盖）。
- 只有当红牌命令都不够时，才去翻 `ops/run-latest-2026-07-10.md`（troubleshooting 附录），doctor 的 Verdict 行会指向它。
