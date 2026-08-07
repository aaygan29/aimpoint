# Environment proposal rubric

Used by maintainers, and by any LLM judge assisting review, to assess proposals before
implementation. Scored 1 to 5 per criterion. **Criterion 2 is a gate: a score of 1 or 2
rejects the proposal regardless of everything else.**

A proposal is roughly a page. It costs an hour; an environment costs weeks.

---

## 1. Safety specificity (weight: high)

*Does this measure a safety-relevant capability, or a general capability wearing safety
language?*

The article's test: "better at coding in Python" is a general capability; "better at
TransformerLens for interpretability research" unblocks a specific safety bottleneck.

| Score | Description |
| --- | --- |
| 5 | Names a specific bottleneck, says who is blocked by it and how, and the capability plausibly comes from practitioner experience rather than from browsing for a topic |
| 3 | Safety-adjacent and plausible, but the bottleneck is asserted rather than evidenced |
| 1 | General capability relabeled. "Better at biology so it can help with pandemics" |

**Reviewer prompt:** if a model got much better at this, name the concrete thing that
becomes possible which is not possible now. If you cannot, score 2 or below.

## 2. Defensive asymmetry (GATE)

*Does competence here have a symmetric offensive use?*

An environment is a reward signal, and a reward signal does not know what the capability is
for. See the insulin-synthesis worked example in [CONTRIBUTING.md](../CONTRIBUTING.md).

| Score | Description |
| --- | --- |
| 5 | The offensive analogue is named explicitly and there is a structural reason competence does not transfer, ideally enforced by what the environment's tools can express |
| 3 | Asymmetry is argued but rests on the topic being benign rather than on the capability being one-directional |
| 1 | Dual-use, or generative in a hazardous domain. **Reject.** |

**Reviewer prompt:** write the most harmful thing a model that maxes this environment could
do better than before. If that sentence is easy to write, the gate fails.

## 3. Judge-free scorability

*Can the headline be computed without an LLM judge?*

| Score | Description |
| --- | --- |
| 5 | Deterministic ground truth: recorded outcomes, simulator execution, a frozen database, a formal check |
| 3 | Mostly deterministic with a judged secondary component that stays out of the headline |
| 1 | Free-text output requiring a judge for the primary score |

Escape hatches that usually work: retrospective holdout against what actually happened,
execution against a simulator, structured claim vocabularies, differential testing.

## 4. Difficulty durability

*Will this still be informative in two model generations?*

The article: *"If in doubt, err on the side of too difficult."*

| Score | Description |
| --- | --- |
| 5 | Frontier models are well short of ceiling, and difficulty comes from the problem being genuinely hard rather than from added steps |
| 3 | Currently hard, plausibly saturating soon |
| 1 | Retrieval or recitation; a good model already ceilings it |

**Reviewer prompt:** be suspicious of difficulty from artificial complexity, and of tasks
found by generating many candidates and keeping whatever the current model fails. That
selects for quirks of one model generation, which the next release removes.

## 5. Reference baseline

*Is there an obvious approach a model must beat, and is it hard?*

| Score | Description |
| --- | --- |
| 5 | A named, implementable policy a competent practitioner would actually use, hard to beat |
| 3 | A baseline exists but is weak |
| 1 | None proposed, so a score would be uninterpretable |

## 6. Feasibility

*Can the proposer build this?*

| Score | Description |
| --- | --- |
| 5 | Data is public and accessible now, scope is bounded, the author has relevant domain experience |
| 3 | Feasible with effort; some data access unresolved |
| 1 | Depends on data that does not exist or cannot be redistributed |

---

## Decision

- **Accept**: criterion 2 scores 4+, criteria 1 and 3 score 4+, nothing below 3.
- **Revise**: criterion 2 scores 4+, something else is weak. Usually fixable in one round.
- **Reject**: criterion 2 scores below 3, or the capability is general with safety framing.

Rejection on criterion 2 is not a judgement of the proposer. The insulin example was the
first idea considered for this repo and it failed this gate; that is what the gate is for.
