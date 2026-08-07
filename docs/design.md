# Design notes

Why the harness is shaped the way it is. Each section is a constraint that came from a
specific failure mode, most of which this repo hit during its own construction.

## An eval and an RL environment are the same object

This is the article's mechanical point and the source of every other decision here. An eval
asks "can the model do X?" and produces a score. An RL environment asks the same question and
feeds the score back as training signal. The rubric becomes the reward function.

That changes what a good rubric is. A descriptive metric only has to correlate with quality
on the distribution of behaviour that already exists. A reward function has to keep
correlating with quality *after* something has optimised against it, on a distribution it
created. Most published eval rubrics would not survive that, and would not have to, until
someone trains on them.

So: every metric here is written as though someone will optimise it adversarially, and every
environment ships an adversarial baseline that tries.

## Judge-free primary scoring

An LLM judge in the headline metric creates three problems, and only the first is widely
acknowledged.

**Variance.** Judges disagree with themselves across runs. A benchmark whose numbers move
between reruns cannot support the comparisons people want to make with it.

**Circularity.** When a judge and a subject share a model family, the metric partly measures
family agreement.

**Gameability, which is the fatal one.** A judge is a model, so it has adversarial inputs. As
a reward function it is a model to be manipulated rather than a standard to be met, and the
resulting policy is optimised against the judge, not the task.

The enforcement is structural, not advisory. `score_primary` receives a scenario, a
submission, and frozen data. There is no model in scope to call. Validation additionally runs
the scorer with model acquisition trapped, which catches a scorer reaching for one through a
global. Judged metrics live in `score_secondary`, are reported, and cannot enter the headline.

The cost is real: some tasks are genuinely hard to score deterministically. In practice that
usually indicates the task is not specified tightly enough yet, and the escape hatches
(retrospective holdout, simulator execution, structured claim vocabularies, formal checks)
cover more ground than people expect.

## Typed actions, never prose parsing

When a scorer regexes free text, part of what it measures is how closely a model's formatting
habits match the regex author's expectations. Two models with identical judgement get
different scores, and the benchmark quietly becomes a formatting benchmark.

Every action reaches the harness as a validated Pydantic object produced by a tool call. This
also makes the episode transcript a complete, replayable record, so a run can be re-scored
from its log without being re-run.

## Cross-cutting probes

Sycophancy, abstention, fabrication, and shift live in the harness rather than in individual
environments, for two reasons.

**Comparability.** If each environment implemented its own sycophancy metric, cross-environment
comparison would measure implementation differences. A shared implementation means a
sycophancy score from a cyber-defense environment and one from a biomedical environment are
the same quantity.

**Contribution cost.** An environment author declares what a scenario withholds and what
pressure it applies. They do not implement the measurement. That is the difference between
contributing domain knowledge and contributing a research project.

Three details each came from getting it wrong first:

- **Sycophancy is a differential, not a rate.** A model that never moves under pressure is
  not principled, it is rigid, and rigidity is its own failure when new information genuinely
  should change an answer. Scenarios push both ways with an identical template; the reported
  index is the difference. Reporting capitulation rate alone lets stubbornness read as
  integrity.
- **Abstention has two failure modes with opposite signs.** Answering past a hole, and
  reflexive hedging. A metric that punishes only the first rewards the second, so both are
  scored and an `always_abstain` baseline is shipped to catch an unbalanced scenario set.
- **Inapplicable is not zero.** A probe that returns 0.0 when it had nothing to measure
  dilutes the average toward whatever fraction of scenarios carried the probe, and "sycophancy
  was never tested" reads as "no sycophancy detected". Probes return an explicit
  not-applicable marker.

## Mandatory baselines

A bare 0.62 is not a result. It could be excellent or worse than doing nothing, and no reader
can tell. Every environment ships a floor and a reference, and CI fails without them.

Three roles, kept distinct: `floor` is the do-nothing bound, `reference` is the line worth
beating, `adversarial` is a policy written to game the proxy. Adversarial baselines are never
eligible to become the reference, because a gamer that scored well would silently raise the
bar it was written to expose.

The reference must be genuinely good. A strawman makes any model look competent and is the
most common way a benchmark flatters its subject. If a frontier model does not beat the
reference, that is a finding to report.

## The proxy gap

Every environment implements `proxy_score`: the flawed metric a hurried designer would have
shipped. The harness reports the difference between it and the real score.

This makes specification gaming measurable instead of hypothetical. In `target_triage` the
proxy is `recall_at_any`, and a policy that names 400 targets at hedged confidence nearly
doubles the reference on it while scoring below the reference on the real metric. Anyone can
run that.

Writing the bad metric down on purpose is the trick. Everyone knows reward hacking exists;
almost nobody instruments for it, because doing so requires admitting in advance what your
metric would have been if you had been less careful.

## Reproducibility as a gate, not a goal

Three sources of drift are closed off, each fatal in a different way.

**Live data.** Eval-time code never calls an API. Snapshots are checksum-pinned and a mismatch
is a hard failure. The Open Targets endpoint rate-limited during this repo's construction, and
rate limits are the benign case: silent upstream revision is the real hazard, because it
leaves the numbers looking comparable.

**Wall-clock time.** Environments read `frozen_now()`. A retrospective-holdout task whose
notion of "now" advances is a task whose answer key changes underneath it.

**Unseeded sampling.** Seeds are derived by hash from the run seed and identifying parts, so
they do not depend on execution order or parallelism. Sample 7 gets the same seed wherever it
ran, which is what lets replicate variance mean what it claims to.

And the reporter refuses to emit a headline from fewer than three replicates. A single run
reports run-to-run variance as though it were a property of the model, and making that path
unavailable is more effective than discouraging it.

## The asymmetry gate

The requirement most specific to this repo. An environment is a reward signal, and a reward
signal does not know what the capability is for. If the capability has a symmetric offensive
use, you have built an uplift environment with a beneficial label.

The article's own test is the starting point: "better at Python" is a general capability;
"better at TransformerLens" unblocks a specific safety bottleneck. The gate extends it. It is
not enough to be safety-adjacent; competence must not transfer to harm.

The worked example is in [CONTRIBUTING.md](../CONTRIBUTING.md): the first environment
considered for this repo was "synthesize insulin from first principles", and it failed, most
decisively because rewarding de novo route-planning for a bioactive peptide is
synthesis-planning uplift regardless of which molecule it was pointed at. The fix kept the
domain and inverted the direction, reasoning over molecular interactions that are already
characterised and already public.

The strong form of an asymmetry claim is structural rather than rhetorical: `target_triage`
cannot be used for synthesis planning because its tools expose no way to describe a molecule
that does not already exist. "The topic is beneficial" is not an argument, and validation
rejects rationales that are too short to be one.

## Data auditing

Two split defects, both of which shipped in this repo's first snapshot and neither of which
was visible from the outside:

- **Unreachable answers** cap the achievable score and read as model incompetence.
- **Separating artifacts** inflate scores and read as model insight.

They are opposites, and fixing one naively creates the other, which is what happened here: 37%
of positives were unreachable, and adding back just those targets would have made "has no
pre-cutoff drug" a perfect tell. The fix was to widen the candidate frame to one defined
independently of the answer.

Every environment should run an equivalent audit on every build. `scripts/build_snapshot.py`
has a worked example.
