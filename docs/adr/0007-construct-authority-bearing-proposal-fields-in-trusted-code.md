# Construct authority-bearing Proposal fields in trusted code

Models and model-visible tools may produce only a typed domain Intent Payload. A trusted Proposal Factory binds that payload to the actual principal, target, lifecycle, version, provenance, Proposal identity, and idempotency context; none of those authority-bearing fields are model-controlled. L2 then reloads current facts and adjudicates the resulting Proposal Envelope. This prevents probabilistic output from asserting its own authority while keeping domain intent expressive.
