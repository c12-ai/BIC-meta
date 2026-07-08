# Prior Art: LLM Safety Judges Over-Rejecting Valid Domain Content

**Date:** 2026-06-05
**Author:** Research subagent
**Scope:** Open-web review of LLM safety judge / content moderation over-refusal literature, with bias toward chemistry & scientific/technical domains. Informs M4 decision between 3a (tune prompt), 3b (swap model), 3c (narrow scope).

---

## TL;DR

- **Over-rejection is a recognized, systemic failure mode of small "judge" LLMs on scientific/technical content.** Vendor benchmarks (Llama Guard 3 reports ~5% FPR) drastically understate production reality (12–23% FPR on educational/medical/technical content). The root cause across the literature is **surface-feature matching**: RLHF-aligned classifiers flag content that *resembles* unsafe content (keywords, named entities like reagents) without parsing context. This is exactly the failure pattern we see with `user_admittance` on "CC Spec" / column chromatography.
- **Production chemistry LLMs do not rely on a single LLM safety judge for the off-topic/capacity branch.** ChemCrow (Nature MI, IBM/EPFL) uses **hard-coded rule-based guardrails** (PubChem lookups, controlled-substance lists) for chemistry-specific safety and reserves the LLM for reasoning. The industry-wide pattern is a **layered/hybrid** architecture (rules + small classifier + optional LLM), not "small LLM judge as sole gate."
- **The single highest-leverage prompt fix in the literature is contrastive few-shot calibration with explicit domain whitelisting + chain-of-thought before verdict.** FalseReject, OR-Bench, and DCR all converge on: show the judge pairs of *superficially-toxic-but-benign* vs *actually-toxic* examples in the target domain, ask it to reason first then emit a structured verdict, and bias toward ALLOW on ambiguity. This is cheap to try and is the prerequisite for evaluating whether a model swap is actually needed.

---

## 1. Domain-specific LLM safety judges — known failure modes

**Finding: Production false-positive rates on scientific/technical content are 3–5× higher than vendor benchmarks claim.**

- **[Llama Guard Benchmark Review (aimoderationtools.com)](https://aimoderationtools.com/posts/llama-guard-benchmark-review/)** — Independent eval reports Llama Guard 3 8B vendor FPR of ~5.2% on standard benchmarks but **12% FPR on educational history content, 17% on fiction with dark themes, and 23% FPR on medical content discussing self-harm in clinical context**. Credibility: independent benchmark site, no vendor affiliation. Operational framing matches our situation: "users can't reliably access legitimate content, [creating] abandonment, manual review burden, and appeals queues."
- **[ChemSafetyBench (arXiv 2411.16736)](https://arxiv.org/html/2411.16736v1)** — The first chemistry-specific safety benchmark. Explicitly states "existing alignment efforts for LLMs have paid little attention to safety in chemistry. Current approaches either emphasize general chemistry knowledge while overlooking safety or attempt to enhance safety in general QA settings without adequately covering the chemical domain." Uses GPT-4o + PubChem lookups as judge — not a small LLM, and not text-only. Credibility: peer-review-track arXiv, multi-institution authors.
- **["Know Thy Judge" (arXiv 2503.04474)](https://arxiv.org/pdf/2503.04474)** — Meta-evaluation of safety judges. Finds that "small changes such as the style of the model output can lead to jumps of up to 0.24 in the false negative rate on the same dataset" and judges are easily fooled by adversarial perturbations. Implication: safety judges are brittle on **stylistic variation alone**, which means a chemistry user phrasing the same query differently can flip the verdict. Credibility: arXiv preprint, methodologically rigorous meta-eval.
- **[LLM Safeguard is a Double-Edged Sword (arXiv 2410.02916)](https://arxiv.org/pdf/2410.02916)** — Demonstrates ~30-character adversarial prefixes can cause Llama Guard 3 to over-reject 97% of benign user requests. Credibility: arXiv. Shows over-refusal is exploitable, not just inconvenient.
- **[Qwen3Guard Technical Report (arXiv 2510.14276)](https://arxiv.org/pdf/2510.14276)** — The Qwen team's own guard model acknowledges: "safety annotations used to train Qwen3Guard inevitably reflect the biases and cultural assumptions embedded in the source datasets ... the model may disproportionately flag content from certain demographic, linguistic, or cultural groups as 'unsafe' or 'controversial,' even when such content is contextually appropriate." StreamGuard variant explicitly noted to have **higher false-positive rates** due to partial-context classification. Credibility: official Qwen team technical report.

**Takeaway for M4:** Our observed behavior (`user_admittance` rejecting CC Spec) is the canonical failure mode of a small RLHF-aligned judge on a technical-domain keyword. We are not unlucky. This is the modal outcome.

---

## 2. Two-pass guard architecture — is "small LLM judge as first gate" industry standard?

**Finding: It is *common* but not *recommended* as a sole gate. The state of the art is a layered/hybrid system. Production chemistry LLMs explicitly use rules-first.**

- **[ChemCrow / Nature Machine Intelligence (s42256-024-00832-8)](https://www.nature.com/articles/s42256-024-00832-8)** + **[PMC mirror](https://pmc.ncbi.nlm.nih.gov/articles/PMC11116106/)** — The reference production chemistry LLM agent. Safety architecture: **"ChemCrow follows a set of hard-coded guidelines by checking that the queried molecule is not a known controlled chemical."** Safety is enforced by deterministic lookups against PubChem and a controlled-chemical list, not by an LLM judge over free-text. The LLM only does reasoning *after* the rule-based gate decides the substance is permissible. Credibility: peer-reviewed Nature journal, IBM Research collaboration.
- **[Essential Guide to LLM Guardrails (Medium, Sunil Rao)](https://medium.com/data-science-collective/essential-guide-to-llm-guardrails-llama-guard-nemo-d16ebb7cbe82)** — Surveys Llama Guard, NeMo Guardrails. Notes NeMo runs a **dialog manager (Colang) over programmable rails** at runtime as the canonical pattern, with the LLM judge being one of several rails (topical, execution, content) not the only rail. Credibility: practitioner survey, reasonable but not academic.
- **[Lightweight Safety Guardrails Using Fine-tuned BERT (arXiv 2411.14398)](https://arxiv.org/html/2411.14398v1)** — Argues for replacing 7B+ LLM judges with **67M-parameter Sentence-BERT** classifiers that achieve "comparable performance on the AEGIS safety benchmark" at ~100× lower latency/cost. Two-stage: fine-tuned embeddings + simple classifier head. Credibility: arXiv, reasonable but newer work.
- **["Catastrophic Collapse of Safety Classifiers under Embedding Drift" (arXiv 2603.01297)](https://arxiv.org/pdf/2603.01297)** — Critical counterpoint to embedding-only approaches: "embedding perturbations as small as 2% of the embedding norm reduce state-of-the-art toxicity detectors to near-random performance yet predicted confidences remain high, producing **dangerous silent failures.**" This is why pure embedding gates don't replace LLM judges in high-stakes settings. Credibility: arXiv.
- **[Off-Topic Prompt Detection (arXiv 2411.12946)](https://arxiv.org/html/2411.12946v1)** — Directly relevant to our `user_admittance` use case ("is this query on-topic for the assistant?"). Recommends bi-encoder or cross-encoder fine-tuned on synthetic on-topic/off-topic pairs, framing the gate as **relevance scoring** rather than safety classification. Credibility: arXiv.

**Takeaway for M4:** The industry pattern that actually ships in chemistry contexts (ChemCrow) is **rule-based gate + LLM for reasoning, not LLM-as-judge + LLM for reasoning**. Off-topic detection specifically has dedicated lightweight approaches (cross-encoders, embedding similarity) that are purpose-built for it. This is independent corroboration for option 3c.

---

## 3. Qwen3 family characteristics on classification

**Finding: Qwen3 small variants exhibit a documented "controversial" / over-flagging bias acknowledged by the Qwen team itself. Qwen3Guard's default behavior bins ambiguous content as unsafe.**

- **[Qwen3Guard Technical Report (arXiv 2510.14276)](https://arxiv.org/pdf/2510.14276)** — Direct quote: Qwen3Guard outputs three labels (safe / unsafe / **controversial**) and "the controversial label is merged with unsafe" in their reported metrics. "Without this merging, Qwen Guard's recall would drop to 46.75%, ranking it 10th rather than 1st." Translation: the model's headline performance numbers are achieved by **defaulting ambiguous cases to reject**. This is the exact behavior we're observing on CC Spec. Credibility: official Qwen team paper.
- **[Benchmarking Open-Source Safety Guard Models (arXiv 2605.28830, ICLR 2026 workshop)](https://arxiv.org/html/2605.28830)** — Comprehensive benchmark of 14 open-source guard models on 79K samples across 8 NIST categories. Finds "many widely-deployed models exhibit dangerous conservatism, missing up to 75% of harmful content" — i.e., the reject-bias does not even guarantee good harm catch rate. Credibility: ICLR workshop paper.
- **["Explicit Reasoning Makes Better Judges" (arXiv 2509.13332)](https://arxiv.org/pdf/2509.13332)** + **[Qwen3 judge study (arXiv 2603.12246)](https://arxiv.org/html/2603.12246v1)** — Both find that Qwen3 small variants (0.6B, 1.7B, 4B) benefit substantially from **thinking-mode / CoT** before verdict on judge tasks, especially on "Safety" and "Chat Hard" splits of RewardBench. Non-thinking 4B Qwen3 is materially worse than thinking-mode at distinguishing benign from harmful. Credibility: arXiv preprints.
- **Note on "qwen3.6-flash":** The web does not surface a model card under that exact name. Closest match in literature is Qwen3 4B / Qwen3Guard 4B / Qwen3-Flash naming variants used in vendor APIs. If our model is the Alibaba Cloud Bailian "qwen-flash" series built on Qwen3, the technical report findings above are the most relevant prior art available.

**Takeaway for M4:** Qwen3 small variants have an explicit, vendor-acknowledged conservative bias on classification, **and** the same family benefits disproportionately from CoT-before-verdict. Two implications: (a) the over-rejection we see is consistent with the model family default, not a bug, (b) a prompt-engineering fix forcing reasoning before verdict has documented family-specific benefit.

---

## 4. Prompt patterns that reduce over-rejection

**Finding: Three techniques converge across multiple papers: contrastive few-shot calibration, chain-of-thought before verdict, and "default to ALLOW on ambiguity."**

- **[FalseReject (arXiv 2505.08054 / project page)](https://false-reject.github.io/)** — Dataset + training approach with 44 safety categories. Core insight: "context-aware safety" responses that **acknowledge multiple interpretations**, explain the safe context with reasoning, clarify why the unsafe interpretation would be problematic, then provide guidance. Their CoT variant (FalseReject-Train-CoT) is specifically designed for reasoning models. Even without their training data, the **prompt pattern** (force the judge to enumerate interpretations before deciding) is transferable. Credibility: arXiv, well-cited.
- **[OR-Bench (arXiv 2405.20947, ICML 2025)](https://arxiv.org/abs/2405.20947)** — Confirms **few-shot examples consistently help** judges distinguish "seemingly toxic but benign" vs actually toxic. The hard subset construction methodology (ensemble agreement) is itself a template for self-checking. Credibility: ICML 2025 poster, peer-reviewed.
- **[Discern Truth from Falsehood / DCR (arXiv 2603.03323)](https://arxiv.org/pdf/2603.03323)** — Contrastive refinement: training/prompting judges with paired examples (toxic vs superficially-toxic-benign) "effectively reduces over-refusal while preserving the safety benefits of alignment." Credibility: arXiv.
- **[Beyond Over-Refusal (arXiv 2510.08158)](https://arxiv.org/pdf/2510.08158)** — Post-hoc, inference-time mitigations that **require no retraining**: ignore-word instructions ("the presence of word X alone is not grounds to reject"), prompt rephrasing, attention steering. "Substantially improve compliance on safe prompts." Critical caveat: "may also weaken safety protections." Credibility: arXiv.
- **[Judge Prompt Engineering (Statsig)](https://www.statsig.com/perspectives/judgepromptengineeringbias)** — Practitioner notes consolidate the pattern: clear criteria, strict output schema, short rationales, anchor to reference exemplars, role-based prompts. Credibility: industry practitioner blog, useful checklist.
- **[Anthropic Constitutional AI (arXiv 2212.08073)](https://arxiv.org/pdf/2212.08073)** — Anthropic's own field report on over-refusal: early CAI models replied to "hey" with "I apologize, my previous responses were inappropriate and harmful." Root cause was "training dataset had a large fraction of harmlessness data, causing the preference model to reward harmless responses much more than helpful responses." Fix: **reweight to balance helpfulness vs harmlessness** explicitly. Translates at prompt-engineering layer to: weight helpfulness explicitly in judge prompt, do not let the judge optimize for harmlessness alone. Credibility: canonical paper.

**Takeaway for M4:** The Phase 3a prompt fix that has the most prior-art support is:
1. **Force chain-of-thought before verdict** ("first enumerate possible interpretations of this query, then decide").
2. **5–10 contrastive few-shot examples** specifically using on-topic chemistry queries that *look* unsafe (CC, retrosynthesis, reagent handling) paired with their PASS verdicts, and one or two clearly off-topic examples with REJECT verdicts.
3. **Explicit ALLOW bias on ambiguity** ("when in doubt about whether a query is on-topic chemistry, default to PASS — the downstream reasoning agent will handle scope").
4. **Domain whitelist** ("queries about column chromatography, retrosynthesis, recrystallization, distillation, reagent selection, and lab protocols are within scope").

---

## 5. When to give up on the LLM judge

**Finding: Signals to swap or replace the judge include (a) family-acknowledged conservative bias that prompt-tuning can't override, (b) high stylistic-perturbation variance, (c) latency/cost not justified given a deterministic alternative exists.**

- **["The 30% Blind Spot" (SnailSploit)](https://snailsploit.com/ai-security/rai-judge-blind-spots/)** — Industry security commentary: small LLM judges have systematic blind spots that cannot be fully closed with prompt engineering. Credibility: industry blog, lower than arXiv but corroborative.
- **["Know Thy Judge"](https://arxiv.org/pdf/2503.04474)** — Re-cited here: if your judge's verdict shifts by 0.24 FNR purely from output-style changes, no amount of prompt engineering will stabilize it. This is a model-capacity ceiling. Signal to swap.
- **[ChemCrow](https://www.nature.com/articles/s42256-024-00832-8)** — Re-cited: when the production gold standard in your domain uses **rules + tool calls** rather than an LLM judge, that's a signal the LLM judge architecture is the wrong abstraction for the gate. Signal to narrow scope (3c) or replace gate entirely.
- **[Lightweight Safety Guardrails (arXiv 2411.14398)](https://arxiv.org/html/2411.14398v1)** — Argues for fine-tuned BERT embeddings as replacement when latency and cost are dominant. Signal for 3b alternative: don't swap to a *bigger* LLM judge, swap to a *purpose-built classifier* for off-topic detection.
- **[Off-Topic Prompt Detection (arXiv 2411.12946)](https://arxiv.org/html/2411.12946v1)** — Specifically frames the "is this query relevant to the assistant?" gate as a fine-tuned cross-encoder problem, not a generative LLM problem. Credibility: arXiv.

**Signals that justify Phase 3b (swap model):**
- After prompt-engineering all four techniques from Section 4, FPR on a curated chemistry test set remains > ~10%.
- Stylistic variance of the same query (rephrasings, casing, terminology) causes verdict flips at the same rate as the underlying content variance. This is a model-capacity ceiling.
- Vendor-acknowledged conservative bias (which Qwen3Guard report concedes) cannot be tuned away.

**Signals that justify Phase 3c (narrow scope to content-policy only):**
- The "off-topic / capacity" judgment is fundamentally a relevance task, not a safety task, and the literature has dedicated cheaper architectures for it (cross-encoders, embedding similarity).
- ChemCrow precedent: domain-specific rule-based gates are how production chemistry LLMs handle the equivalent decision.
- Defense-in-depth concern (see Conclusion below).

---

## Conclusion: what does the prior art recommend for M4?

**Sequence the work as 3a → (if fails) 3b or 3c, not 3a vs 3b vs 3c as parallel options.** The literature is clear that prompt engineering (CoT + contrastive few-shot + domain whitelist + default-allow) is the cheapest experiment and is well-supported on the Qwen3 family specifically. Run it first, measure on a curated chemistry test set, then decide whether to escalate.

**If 3a is insufficient, the prior art weakly favors 3c over 3b.** ChemCrow's deterministic safety architecture and the cross-encoder off-topic-detection literature both suggest that the off-topic/capacity branch is not a job an LLM judge should be doing in the first place. Swapping to a bigger LLM (3b) helps marginally with conservative bias but doesn't address the architectural mismatch.

**Important caveat to Drake's stated contract.** The literature does **not** support "`user_admittance` is the sole content-safety boundary" as a defensible production posture for a chemistry domain. Every production reference (ChemCrow, NeMo Guardrails, Llama Guard deployment guides) describes **defense-in-depth: multiple rails (input filter + tool-level checks + output filter)**. Specifically:
- Llama Guard documentation explicitly recommends both input and output filtering, not input-only.
- ChemCrow's safety is at the **tool layer** (PubChem lookup before execution), not the input layer — input-layer judging would not catch a benign-looking request that resolves to a controlled substance after entity extraction.
- The "single content-safety gate" pattern is, per the Llama Guard real-world FPR studies, the architecture most prone to either over-rejection (when tuned safe) or under-detection (when tuned permissive).

**This doesn't block Phase 3 work, but it should be surfaced.** If we narrow `user_admittance` scope (3c) to drop the off-topic branch, we should plan a complementary downstream content-policy check before any externally-actuated step (e.g., before robot execution, before generating actionable lab protocols), per the ChemCrow pattern. That is a separate spec change in the M4-or-later horizon, not Phase 3 itself.

---

## Open questions worth deeper research

- **Does Alibaba Cloud's specific "qwen-flash" (qwen3.6-flash) variant have a published model card with classification-task benchmarks?** None surfaced in web search. Worth pulling directly from Alibaba Cloud Bailian docs or the Hugging Face model card if one exists, to confirm the conservative-bias finding for Qwen3Guard generalizes to the exact variant we use.
- **What does the current `user_admittance` prompt look like, and which of the four Section 4 techniques is it already applying?** Without this, the "cheapest experiment first" recommendation is partly blind — we may already be doing some of them.
- **What is the latency/cost differential between the current Qwen flash judge and a candidate fine-tuned cross-encoder (Sentence-BERT class) for the off-topic gate?** If 3c becomes the chosen path, a numerical comparison against a 67M-param classifier is the practical next step from the Lightweight Safety Guardrails paper.
