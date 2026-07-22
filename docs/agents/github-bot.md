# GitHub Bot 身份：c12-apex-dev

AI agent 做 GitHub 写操作（提 PR、建/评 issue 等）统一用 org 级 GitHub App
**c12-apex-dev**（署名 `c12-apex-dev[bot]`），不再借用个人账号。私钥只存在铸造机
aws-test 的专用账户 **`ghmint`** 名下，其 ssh 公钥全部钉了 forced command：
`ssh bic-mint` 只会铸出 1 小时 token，拿不到 shell、读不到私钥——**铸币权 ≠ 读钥权**，
能碰私钥的只有箱管理员（sudo）。本地 `scripts/gh-app/gh-app-token.sh` 无钥匙时即走
这条 ssh，token 本地缓存 55 分钟复用。bot 不能 approve 自己的 PR，"人工 admin merge"
这道闸不受影响。

- App: https://github.com/organizations/c12-ai/settings/apps/c12-apex-dev
  （app id `4362356`，bot uid `307868801`）
- 铸 token 脚本：`scripts/gh-app/gh-app-token.sh`（免配置：installation 自动发现，
  token 缓存 55 分钟复用）

## 同事一次性接入

不需要团队部署 key，与部署权限完全解耦：

1. 把自己的个人公钥（`~/.ssh/id_ed25519.pub`）发给管理员，加进铸造机 `ghmint` 的
   `authorized_keys`（forced-command 前缀见 `ops/` 施工记录；离职收权 = 删这一行）。
2. `~/.ssh/config` 加：
   ```
   Host bic-mint
     HostName ec2-43-192-79-141.cn-northwest-1.compute.amazonaws.com.cn
     User ghmint
     IdentityFile ~/.ssh/id_ed25519
     IdentitiesOnly yes
   ```
   （公网 IP 需在 office-ips 白名单内，同部署一致。）
3. 验证：
   ```bash
   scripts/gh-app/gh-app-token.sh --check
   # OK  identity: c12-apex-dev[bot] ...
   ```

完成。本机不落任何秘密；个人的 `gh auth` / git 配置一概不动。
（铸造机别名可用 `BIC_GH_APP_SSH` 覆盖；管理员/测试可用 `BIC_GH_APP_KEY=<pem>` 走本地钥匙。）

## Agent 怎么用（无感的关键）

Agent 在做 gh 写操作前铸一次 token（55 分钟内重复调用走缓存，免费）：

```bash
export GH_TOKEN=$(scripts/gh-app/gh-app-token.sh)
gh pr create ...          # 作者显示为 c12-apex-dev[bot]
gh issue create ...
```

只影响当前 shell 的 gh 调用；不 export 时 gh 回落到个人身份。读操作无所谓身份，
不必强求。

以 bot 身份 commit（可选，通常保留人类/个人署名即可）：

```bash
git -c user.name='c12-apex-dev[bot]' \
    -c user.email='307868801+c12-apex-dev[bot]@users.noreply.github.com' commit ...
```

以 bot 身份 push（可选；默认大家走个人 ssh key 即可）：

```bash
git config --global credential.useHttpPath true
git config --global 'credential.https://github.com/c12-ai.helper' \
  '!<BIC-meta 绝对路径>/scripts/gh-app/gh-app-token.sh --credential'
# 仅对 https://github.com/c12-ai/* 生效，个人仓不受影响
```

## CI 里用同一身份

不要把 pem 发给 workflow 手工签 JWT——用官方 action：

```yaml
- uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ vars.C12_APEX_DEV_APP_ID }}
    private-key: ${{ secrets.C12_APEX_DEV_PRIVATE_KEY }}
```

（org 级 secret/variable 配一次，全 org workflow 可用。）

