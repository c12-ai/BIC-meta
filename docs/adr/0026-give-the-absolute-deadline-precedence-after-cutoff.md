# Give the absolute deadline precedence after cutoff

An authorized cancellation may commit only when L2's authoritative terminal decision occurs strictly before the Turn's immutable `execution_deadline_at`; equality or any later decision selects timeout even if the watchdog has not run yet. The cancellation path may help persist or observe that timeout and returns the non-cancellation `already_terminal` disposition, keeping timeout semantics independent of scheduler delay while leaving committed Proposal and Outbox lifecycles untouched.
