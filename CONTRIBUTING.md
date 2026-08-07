# Contributing to Aimpoint

Welcome. This repo builds open-source environments for the capabilities we want AI to have,
following the framing in
[Give AI companies something to aim at](https://blog.bluedot.org/p/give-ai-companies-something-to-aim).

**Why contribute?**

1. **Labs optimize for what benchmarks measure.** An environment you build is a target
   frontier developers can aim at. That is the entire theory of change.
2. **Your domain knows its own bottlenecks.** The article's recommended method for finding
   them is to reproduce a real project and note where it broke, or to ask practitioners what
   their tools cannot do. You already have that knowledge; most benchmark authors do not.
3. **Authorship.** Contributors with merged environments are credited as authors on the
   Aimpoint paper and listed in [AUTHORS.md](AUTHORS.md). Maintainers are invited from among
   people who have merged an environment and reviewed others.

---

## The process

Three stages, deliberately curated. Quality matters more than count here, because a bad
environment does not merely fail to help, it points optimization pressure somewhere wrong.

### 1. Propose

Open a [Environment Proposal issue](../../issues/new?template=environment-proposal.yml)
before you build. A proposal is roughly a page and answers the four questions in
[rubrics/environment-proposal.md](rubrics/environment-proposal.md). Maintainers respond on
the issue, and proposals are cheap to revise while expensive to un-build.

Proposals are graded against the rubric with particular weight on two things:

- **Is this safety-specific or just generally useful?** The article's test: "better at
  Python" is a general capability wearing safety language. Yours must unblock a *specific*
  bottleneck, and you must name it.
- **Does it pass the asymmetry gate?** See below. This is the most common reason a proposal
  is sent back.

### 2. Build

Once the proposal is accepted, build it following
[docs/adding-an-environment.md](docs/adding-an-environment.md) and open a pull request.
CI runs the full contract check. Expect a few rounds of review; most environments need
them.

### 3. Review

Contributors who have merged an environment are invited to review others. Reviewing is
where most of the quality comes from, and the reviewer guide is
[REVIEWING.md](REVIEWING.md).

---

## The asymmetry gate

**Read this before proposing.** It is the requirement most specific to this repo and the
one most proposals miss.

An environment is a reward signal. A reward signal does not know what your capability is
*for*. If the capability you are training has a symmetric offensive use, you have built an
uplift environment with a beneficial label on it.

The worked example, which is a real proposal that was rejected during this repo's design:

> *"Given a patient profile, have the model synthesize insulin from first principles and
> chemical knowledge."*

It sounds unambiguously beneficial. It is not usable, for four reasons, and the fourth is
the disqualifying one:

1. **The patient profile does nothing.** Human insulin is one fixed molecule. A patient with
   renal impairment does not get a different molecule, they get a different dose. The two
   halves of the task never interact.
2. **It is not gradeable.** A synthesis route is prose, so scoring needs a judge, and a
   judged headline metric is the highest-variance grader available.
3. **It is memorized, not hard.** Recombinant insulin production is textbook. Frontier
   models hit ceiling immediately, failing the article's "desirable difficulty" bar.
4. **It points the wrong way.** Rewarding de novo route-planning for a bioactive
   disulfide-bonded peptide is synthesis-planning uplift. The gradient does not know insulin
   is benign, and that capability generalizes to peptide toxins.

The fix preserved the domain and inverted the direction: reason over molecular interactions
that are **already characterized and already public**, never generate new chemistry. That is
[`target_triage`](environments/biomedical_rd/target_triage/), and its
`asymmetry_claim` is enforced by the tools, which expose no way to describe a molecule that
does not already exist.

**Your `asymmetry_claim` must:** name the capability, name its closest offensive analogue,
and say specifically why competence does not transfer. "The topic is medicine" is not an
argument. `aimpoint validate` rejects rationales under 40 words; reviewers reject ones that
are long but empty.

If your environment is genuinely dual-use, say so in the proposal. Some are worth building
with mitigations and some are not, and that is a conversation to have before you write code.

---

## What makes a good environment

**Difficulty that survives.** Aim well beyond current frontier ability. The article's
guidance: *"If in doubt, err on the side of too difficult."* Difficulty should come from the
problem being real, not from artificial complexity. Longer horizons, cascading errors, real
data, and genuine expert judgement are the good sources. Adding steps is not.

**Judge-free primary scoring.** If you cannot see how to score your task without an LLM
judge, that usually means the task is not specified tightly enough yet. Common escape
hatches: retrospective holdout against recorded outcomes, execution against a simulator,
structured claim vocabularies, and checking against a frozen database. Judged metrics belong
in `score_secondary`, where they are reported and never enter the headline.

**A reference baseline that is hard to beat.** Write the policy a competent person with the
same data and no special insight would use. If a model cannot beat it, that is a finding
worth publishing, not a bug to hide.

**A proxy metric you wrote on purpose.** Implement `proxy_score` returning the flawed metric
a hurried designer would have shipped. The harness reports the gap. This is how
specification gaming becomes measurable instead of hypothetical.

**Honest limits.** `known_limits` in your `environment.toml` is required and reviewers read
it before the results. State what your ground truth does not mean, where leakage might
remain, and how small your sample is. An environment whose limits section is thin gets more
scrutiny, not less.

---

## Areas

| Area | Scope |
| --- | --- |
| `safety-research` | Interpretability tooling, eval construction, alignment research workflows |
| `cyber-defense` | Vulnerability patching, incident triage, hardening, detection engineering |
| `pandemic-preparedness` | Surveillance, outbreak response, countermeasure logistics |
| `information-integrity` | Fact-checking, provenance, coordinated-behavior detection |
| `biomedical-rd` | Target triage, trial design, pharmacovigilance |

The first four are the article's list. `biomedical-rd` is our extension, added because a
contribution needed a home. Propose new areas in a discussion.

---

## Development

```bash
uv sync
uv run pytest          # full pipeline against a mock model, no API key, no cost
uv run ruff check .
uv run aimpoint validate
```

Environments live at `environments/<area>/<env_slug>/`. Directory names must be valid Python
identifiers (underscores, not dashes) because they are imported as packages. Discovery is
automatic: drop in a folder with an `environment.toml` and the harness finds it. You never
edit anything outside your own directory.

## Conduct and licensing

By contributing you agree your work is licensed under Apache-2.0. Be constructive in review.
Environments make claims about what is beneficial, so disagreement is expected and should
stay technical.

## Contact

Open an issue or a discussion. For anything sensitive, including a dual-use concern about an
environment already merged, email the maintainer listed in [AUTHORS.md](AUTHORS.md) rather
than opening a public issue.
