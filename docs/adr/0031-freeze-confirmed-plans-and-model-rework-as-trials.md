# Freeze confirmed Plans and model rework as Trials

Once confirmed, an Experiment Plan's ordered Step structure is immutable; normal progression changes only dedicated L2-owned progression facts, and same-Step rework creates a new Trial under the same Step. V1 rejects structural Plan changes and introduces no Revision model, API, or persistence fields. If a future approved product need requires changing remaining Steps, it must use a new confirmed Plan identity while preserving completed history rather than weakening the confirmed-Plan invariant.
