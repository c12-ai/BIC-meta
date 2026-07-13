# Auth 加固后的 bench 操作清单(2026-07-13 定档)

背景:lab-service 强制校验 Keycloak JWT(豁免仅 `GET /`、`/health*`),portal 带用户
token,agent BE 带 `bic-agent-service` 服务账号 token(client-credentials)。
**配置缺失的症状是 401 风暴而不是起不来**——服务健康、页面能开,但业务调用全挂。
`make up` 与 `make doctor` 已把本清单的绝大部分自动化;人工步骤只剩「重启」。

## 例行升级(拉最新 main 后)

```bash
# 1. 六仓全拉:BIC(meta)、BIC-infra、BIC-agent-service、BIC-agent-portal、
#    BIC-lab-service、mars_interface_mock
# 2. 从 meta 根:
make up          # 幂等:种 Keycloak client、自愈 auth env 键、依赖同步、健康门
# 3. 显式重启(make up 跳过已健康服务 → 老进程跑老代码,这步不能省):
bash scripts/bic-env/restart.sh lab
bash scripts/bic-env/restart.sh BE
bash scripts/bic-env/restart.sh mock
# 4. 验收:
make doctor      # 期望全绿,重点看「Auth (lab JWT enforcement)」三张卡
```

## `make up` 自愈了什么(append-only,已有值永不覆盖)

| 文件 | 键 | dev 默认值 |
|---|---|---|
| BE `.env` | `KEYCLOAK_CLIENT_ID` | `bic-agent-service` |
| BE `.env` | `KEYCLOAK_CLIENT_SECRET` | `bic-agent-service-dev-secret` |
| lab `.env` | `KEYCLOAK_ISSUER_URL` | `http://localhost:18080/realms/bic` |

LAN 口径 bench(issuer 非 localhost,如 `192.168.12.150`)手动改 lab 的
`KEYCLOAK_ISSUER_URL` 为 doctor 显示的实测 issuer(必须逐字节一致);自愈不会动它。

## `make doctor` 的三张 Auth 卡

1. **BE secret**:BE `.env` 是否携带 `KEYCLOAK_CLIENT_SECRET`(缺 → 红卡+修复命令)
2. **401 探针**:裸请求 `/preparations/racks` 应 401。若 200:`.env` 有
   `LAB_AUTH_MODE=off` → 黄卡(显式调试姿态);没有 → 红卡「疑似旧进程诈尸」,
   修复:`pkill -KILL -f BIC-lab-service; bash scripts/bic-env/restart.sh lab`
3. **服务 token 往返**:`get-token.sh` 铸 token 打 lab 应 200(失败多为 issuer
   不一致或 client 未种)

## 日常习惯

- 手动 curl / Apifox 调 lab:带 `-H "Authorization: Bearer $(scripts/bic-env/get-token.sh)"`
  (token 300s 有效,过期重取);CLAUDE.md 的 reset 示例已带此头
- 逃生阀:lab `.env` 追加 `LAB_AUTH_MODE=off` + 重启 = 回到无鉴权(启动 WARN),
  排查完撤掉再重启,doctor 的黄卡会提醒
- 现场(field)部署有独立清单与 blocker:见 BIC-meta#297,**#297 落地前禁止把含
  lab#112 的镜像 roll 到现场**

## 已知尾款(不阻塞 bench)

- BIC-meta#296:开闸后仍裸调 lab 的孤儿调用方(e2e-runner 手册 curl、demo playbook、
  BE tests/fixtures 与脚本)+ BE 入站校验器 kid 缓存 TTL 对齐
- BIC-agent-portal#80:Playwright 两族对 #74 UI 重构的整体漂移(与 auth 无关)
