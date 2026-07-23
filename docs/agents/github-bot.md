# GitHub Bot Identity: c12-apex-dev

**Fully autonomous** AI sessions (cron jobs, batch pipelines, unattended dispatch) perform GitHub
writes (opening PRs, creating/commenting on issues) as the org-level GitHub App **c12-apex-dev**
(authored as `c12-apex-dev[bot]`) — never as a borrowed personal account. Interactive development
(a developer directing an agent) signs as the developer instead; see the ruling below. The private
key lives only on the mint host (aws-test), under the dedicated **`ghmint`** account whose ssh
identities are all pinned to a forced command: `ssh bic-mint` can only emit a fresh 1-hour token —
no shell, no reading the pem. **Mint access is not key access**; only the box admin (sudo) can
reach the key. With no local key configured, `scripts/gh-app/gh-app-token.sh` runs that ssh and
caches the returned token for 55 minutes. The bot cannot approve its own PRs, so the human
admin-merge gate is unaffected.

- App: https://github.com/organizations/c12-ai/settings/apps/c12-apex-dev
  (app id `4362356`, bot uid `307868801`)
- Token script: `scripts/gh-app/gh-app-token.sh`. Overrides: `BIC_GH_APP_SSH` (mint alias,
  default `bic-mint`), `BIC_GH_APP_KEY=<pem path>` (local-key source for the admin and tests —
  skips ssh).

## When to use the bot vs a personal identity (ruling)

Split by **who drives the session**, not by whether AI typed the text:

- **Fully autonomous session → bot**: cron jobs, batch pipelines, unattended dispatch (nightly
  S1/S2/S3 batches, CI-triggered ops). No human is present, so signing as any person would be
  false; the bot byline tells reviewers to apply machine-output scrutiny, and one query audits
  everything the AI did.
- **Interactive session → the developer's own identity**: a developer directing an agent to write
  code, open PRs, or file issues — the developer is the author, the agent is the keyboard. Use
  your own `gh auth`; **nothing to configure**.
- Review / approve / merge / product rulings: always a human, always personal (the bot cannot
  approve its own PRs anyway).

Consequently **most teammates need nothing from this page**; only operators of unattended
pipelines need the setup below.

## One-time setup (operators of unattended pipelines only)

No shared deploy key involved — fully decoupled from deploy access:

1. Send your personal public key (`~/.ssh/id_ed25519.pub`) to the admin, who adds it to
   `ghmint`'s `authorized_keys` on the mint host (with the forced-command prefix; offboarding =
   deleting that one line).
2. Add to `~/.ssh/config`:
   ```
   Host bic-mint
     HostName ec2-43-192-79-141.cn-northwest-1.compute.amazonaws.com.cn
     User ghmint
     IdentityFile ~/.ssh/id_ed25519
     IdentitiesOnly yes
   ```
   (Your public IP must be in the office-ips whitelist, same as for deploys.)
3. Verify:
   ```bash
   scripts/gh-app/gh-app-token.sh --check
   # OK  identity: c12-apex-dev[bot] ...
   ```

Done. No secret ever lands on your machine; personal `gh auth` and git config are untouched.

## How autonomous sessions use it

Mint once before GitHub writes (repeat calls within 55 minutes hit the local cache — free):

```bash
export GH_TOKEN=$(scripts/gh-app/gh-app-token.sh)
gh pr create ...          # authored as c12-apex-dev[bot]
gh issue create ...
```

This affects only `gh` calls in the current shell; without the export, `gh` falls back to the
personal identity. Reads work under either identity — don't bother switching for them.

Committing as the bot (optional; keeping the personal author is usually fine):

```bash
git -c user.name='c12-apex-dev[bot]' \
    -c user.email='307868801+c12-apex-dev[bot]@users.noreply.github.com' commit ...
```

Pushing as the bot (optional; the default is everyone's personal ssh key):

```bash
git config --global credential.useHttpPath true
git config --global 'credential.https://github.com/c12-ai.helper' \
  '!<BIC-meta absolute path>/scripts/gh-app/gh-app-token.sh --credential'
# matches only https://github.com/c12-ai/* — personal repos are unaffected
```

## Same identity in CI

Workflows don't ssh to the mint host — use the official action with org-level secrets:

```yaml
- uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ vars.C12_APEX_DEV_APP_ID }}
    private-key: ${{ secrets.C12_APEX_DEV_PRIVATE_KEY }}
```

(Configure the org-level secret/variable once; every org workflow can use it.)
