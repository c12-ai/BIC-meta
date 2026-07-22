# GitHub Bot 身份：c12-apex-dev

AI agent 做 GitHub 写操作（提 PR、建/评 issue 等）统一用 org 级 GitHub App
**c12-apex-dev**（署名 `c12-apex-dev[bot]`），不再借用个人账号。私钥放团队密码库，
每人一次性领到本机固定路径；之后 agent 用 `scripts/gh-app/gh-app-token.sh` 铸
1 小时短期 token，全程无感。bot 不能 approve 自己的 PR，"人工 admin merge" 这道闸
不受影响。

- App: https://github.com/organizations/c12-ai/settings/apps/c12-apex-dev
  （app id `4362356`，bot uid `307868801`）
- 铸 token 脚本：`scripts/gh-app/gh-app-token.sh`（免配置：installation 自动发现，
  token 缓存 55 分钟复用）

## 同事一次性接入（2 分钟）

1. 从团队密码库取 `c12-apex-dev` 的 private key（.pem）：
   ```bash
   mkdir -p ~/.config/bic-v2/gh-app
   # 把密码库里的 pem 存为：
   #   ~/.config/bic-v2/gh-app/private-key.pem
   chmod 600 ~/.config/bic-v2/gh-app/private-key.pem
   ```
2. 验证：
   ```bash
   scripts/gh-app/gh-app-token.sh --check
   # OK  identity: c12-apex-dev[bot] ...
   ```

完成。个人的 `gh auth` / ssh key / git 配置一概不动。

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

## 安全口径

- **唯一秘密是 pem**：只存密码库 + 本机 600 文件；永不进 git、不进聊天记录。
- **轮换**：App 设置页 Generate private key 生成新 key 后旧 key 立即作废——
  泄露时先轮换再排查；同事重新从密码库领新 pem 即可。
- **一键撤销**：org 里 uninstall App，所有 token 立即失效。
- **权限收窄（建议，待办）**：当前 App 勾了 `administration:write`、
  `packages:write`、`merge_queues:write` 等 PR/issue bot 用不上的权限。建议收到：
  Contents RW · Pull requests RW · Issues RW · Metadata R · Checks R ·
  Statuses RW · Workflows RW（agent 会改 `.github/workflows/` 才需要）。
- token 有效期 1 小时，本机缓存文件 `~/.cache/bic-v2/gh-app-token.json`（600）。
