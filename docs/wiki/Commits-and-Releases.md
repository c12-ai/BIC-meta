# Commits and Releases

Commits are normally reviewed through pull requests. Track commits directly only when they need cross-repo visibility and are not naturally represented by a PR or issue.

## Track Commits When

- A commit is release-relevant across multiple repos.
- A commit changes a contract consumed by another repo.
- A hotfix was pushed directly and needs follow-up review.
- A commit documents a migration point or compatibility boundary.

## Do Not Track Commits When

- The commit is already covered by an open PR.
- The commit is local-only or experimental.
- The commit only affects one repo and has no release coordination impact.

## Release Notes

Release notes should summarize:

- Product-facing behavior changes.
- Contract or API changes.
- Migration steps.
- Known risks and follow-ups.
- Verification evidence.
