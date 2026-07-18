
# EcoSentia Checkpoint

**An evidence-aware self-assessment tool for interrogating AI-generated biomimetic design claims — before they reach the workbench.**

![Status](https://img.shields.io/badge/STATUS-MANUSCRIPT%20IN%20PREPARATION-e59aa5?style=for-the-badge&labelColor=2b2b2b)
![Platform](https://img.shields.io/badge/PLATFORM-HUGGING%20FACE%20SPACES-ebb184?style=for-the-badge&labelColor=2b2b2b)
![Scope](https://img.shields.io/badge/SCOPE-GOVERNANCE%20LAYER%2C%20NOT%20A%20GENERATOR-e3a377?style=for-the-badge&labelColor=2b2b2b)
![License](https://img.shields.io/badge/LICENSE-MIT-c2c9d4?style=for-the-badge&labelColor=2b2b2b)
![Validation](https://img.shields.io/badge/VALIDATION-NO%20WET%20LAB%20%2F%20CLINICAL%20CLAIMS-d9dde5?style=for-the-badge&labelColor=2b2b2b)

[**Try the Live App**](https://huggingface.co/spaces/sogi23/EcoSentia) · [**Read the Manuscript (preprint)**](#citation) · [**Report an Issue**](../../issues)

</div>

---

## Table of Contents

- [What This Is](#what-this-is)
- [The Problem It Addresses](#the-problem-it-addresses)
- [What Checkpoint Does](#what-checkpoint-does)
- [What Checkpoint Does *Not* Do](#what-checkpoint-does-not-do)
- [Evaluation States](#evaluation-states)
- [The Five Analytical Lenses](#the-five-analytical-lenses)
- [Quick Start](#quick-start)
- [Example Walkthrough](#example-walkthrough)
- [Repository Structure](#repository-structure)
- [Notes for Reviewers](#notes-for-reviewers)
- [Reproducibility](#reproducibility)
- [Citation](#citation)
- [License](#license)
- [Contributing](#contributing)

---

## What This Is?

**EcoSentia Checkpoint** is the operational component of **EcoSentia**, a human-centric governance framework for AI-assisted biomimetic design. Checkpoint does not generate biomimetic ideas. It structures how a designer interrogates an AI-generated claim, grounding that interrogation in retrieved literature rather than intuition alone.

Given a design claim (e.g., *"an extracellular-vesicle-inspired carrier for targeted drug delivery"*), Checkpoint runs it through a five-step evidence-aware pipeline and returns a navigational — not definitive — assessment.

---

## The Problem It Addresses

Modern AI systems can produce biomimetic suggestions that are fluent and confident but mechanistically ungrounded. A bibliometric analysis of 6,698 publications (2015–2025) underlying this project identified a measurable **governance gap**: rapid growth in optimization- and deep-learning-oriented biomimetic AI research, alongside a marked scarcity of explicit human-oversight vocabulary in the field's indexed literature.

Checkpoint operationalizes a response to that gap: structured, evidence-anchored, phase-appropriate friction — not a rubber stamp, and not a generator of new content.

---

## What Checkpoint Does?

| Step | Function |
|---|---|
| **1. Pathway Classification** | Identifies whether the claim follows a reverse (problem → biology), forward (biology → application), or generative (human–AI co-creation) reasoning pathway. |
| **2. Evidence Retrieval** | Queries **PubMed** and **OpenAlex** for related literature, deliberately using broad-coverage sources rather than a single discipline-specific index. |
| **3. Support-Level Summarization** | Produces a heuristic indicator based on volume and recency of retrieved evidence — a navigational aid, not a validity score. |
| **4. Lens-Tied Risk Screening** | Applies rule-based screening across five lenses to flag common translation risks (e.g., morphology overreach, mechanism gap, context transfer risk, manufacturability assumptions, safety silence). |
| **5. Structured Prompt Generation** | Produces four prompts — evaluation, counter-prompt, uncertainty-mapping, redesign — for continued human interrogation of the claim. |

---

## What Checkpoint Does *Not* Do?

This distinction matters for reviewers, contributors, and users alike:

- Does **not** validate scientific or mechanistic correctness of a claim.
- Does **not** confirm manufacturability, safety, or regulatory compliance.
- Does **not** constitute or replace wet-lab experimentation, animal studies, clinical trials, or physical prototyping.
- Does **not** treat the support-level indicator as a measure of truth — it reflects literature volume and recency only.
- Does **not** make a final go/no-go decision — that responsibility remains with the human evaluator.

---

## Evaluation States

| State | Meaning |
|---|---|
| 🟩 **Grounded** | Reasonably clear mechanism, relevant context, and preliminary evidence support the claim; sufficiently structured for further development. |
| 🟨 **Simulate** | Promising, but requires modeling, prototyping, or additional evidence before responsible advancement. |
| 🟥 **AI Blindspot** | Interrogation reveals major omissions — superficial analogy, missing mechanism, lost context, scale neglect, or unsupported confidence. |

---

## The Five Analytical Lenses

| Lens | Guiding Question |
|---|---|
| **Mechanism** | Is the claim based on a transferable biological mechanism, or only surface resemblance? |
| **Context** | Have the ecological, physiological, and environmental conditions enabling the function been preserved? |
| **Scale** | Does the mechanism remain physically plausible across the biological-to-engineering scale transition? |
| **Manufacturability** | Can the design realistically be fabricated, sourced, and maintained? |
| **Safety** | Have risks, unintended consequences, and domain-specific ethical concerns been made explicit? |

---

## Quick Start

### Try It Online
No installation required — use the hosted app:
👉 **[huggingface.co/spaces/sogi23/EcoSentia](https://huggingface.co/spaces/sogi23/EcoSentia)**

### Run Locally

**Requirements:** Python 3.10+

```bash
git clone https://github.com/<your-username>/EcoSentia-Checkpoint.git
cd EcoSentia-Checkpoint
pip install -r requirements.txt
python app.py
```

The app will start a local server (default: `http://localhost:7860`).

---

## Example Walkthrough

1. Enter a design claim, e.g.: *"A gecko-adhesion-inspired dry adhesive for climbing robots."*
2. Checkpoint classifies the pathway (forward: biology → application).
3. It retrieves relevant PubMed/OpenAlex records and reports a support level.
4. It screens the claim across the five lenses and flags any risks (e.g., *manufacturability assumption*).
5. It returns four structured prompts for further human interrogation before the claim is treated as design-ready.

---

## Repository Structure

```
EcoSentia-Checkpoint/
├── app.py                  # Main application entry point
├── src/
│   ├── retrieval/           # PubMed / OpenAlex query and retrieval logic
│   ├── scoring/              # Support-level heuristic
│   ├── lenses/                # Rule-based risk-screening logic
│   └── prompts/               # Structured prompt generation
├── bibliometric/            # R scripts for the underlying bibliometric analysis
├── docs/                     # Supplementary methodology documents
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Notes

- Checkpoint is a **design-science artifact**, evaluated formatively through cross-disciplinary expert feedback (biomimicry, computational biology, design, engineering) — not a clinically or experimentally validated tool.
- All demonstration cases in the associated manuscript (fog harvesting, extracellular-vesicle nanomedicine, mantis-shrimp armor, microneedle patch, neuromorphic controller, form-only shark-skin claim, and a negative-control case) are reported with exact retrieval parameters, record counts, and timestamps to support reproducibility review.
- The support-level indicator is explicitly **not** a validity score; this is stated both here and throughout the manuscript to prevent misinterpretation during review.
- No claims of prototype construction, wet-lab testing, animal studies, or clinical validation are made anywhere in this repository or the associated manuscript.

---

## Reproducibility

The bibliometric analysis underlying this framework (6,698 records, WoS + Scopus, 2015–2025) is fully scripted in R (`bibliometrix`, `igraph`, `ggraph`, `ggplot2`, `dplyr`, `stringr`, `tidyr`, `viridis`, `scales`). Full query strings, deduplication logic, and harmonization dictionaries are provided under `/bibliometric` and referenced supplementary materials for exact replication.

---

## Citation

This work is currently unpublished (manuscript in preparation). Citation details, including author information and DOI, will be added to this section upon publication.

---

## License

Released under the [MIT License](LICENSE).

---

## Contributing

Issues and pull requests are welcome. Please open an issue before submitting significant changes so the proposed direction can be discussed first.

</div>
```
