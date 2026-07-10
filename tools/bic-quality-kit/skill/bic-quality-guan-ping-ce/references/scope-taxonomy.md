# Repository and Module Mapping

Repository identity always comes from the discovered Git worktree. It is never
guessed from a file name.

The mapping chain is:

```text
changed file -> discovered repository -> explicit or structural module -> test evidence
```

Known BIC business modules are configured in `config/scope-taxonomy.yaml` and
produce `mapping_source: explicit`. The first matching rule is authoritative,
so specific rules precede broad repository rules.

When no rule matches, the analyzer preserves repository-relative source-tree
structure. Source roots include `app`, `src`, `packages`, `services`, `lib`, and
`bic_shared_types`. Examples include `app/inference`, `app/api/routers`, and
`src/pages/chat`. These mappings use `mapping_source: structural` and do not
reinterpret words such as `api`, `events`, `models`, or `client` as business
capabilities.

Files without a stable source-root path remain visible as `unmapped`. Changes
in more than one discovered repository set the factual
`direct_cross_repository` flag; no additional label is derived.

The public scope contract exposes `affected_repositories` with actual discovered
Git repository names, `modules_by_repository` grouping module evidence under
those names, and `direct_cross_repository` as the only cross-repository fact.
