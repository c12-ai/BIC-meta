# Defer workflow-lifetime behavior binding until production requires it

Status: deferred, mandatory before the first production deployment where an experiment may remain active across Agent Service releases.

Current bench and field operations can finish or reset old-path workflows before the one-time cutover. V1 therefore adds no Workflow Behavior Binding, Behavior Target persistence, legacy backfill, cohort admission, binding drain, or version-retention mechanism. Migration code lands on `main` behind disabled internal routing; after the combined gates pass, old-path workflows finish or reset, the default switches once, and legacy routing and code are removed.

Before BIC supports experiments that survive a deployment, this ADR must be reopened and approved with immutable behavior identity, exact component version retention, rollback, in-flight Proposal and Outbox Command handling, active-workflow migration, failure behavior, and history/audit semantics. That production gate cannot infer behavior from a mutable deployment default or permit Turn-, Step-, model-, or failure-controlled fallback. No storage field or external API is reserved before the gate is resolved.
