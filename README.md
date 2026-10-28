# BridgeLLM

An early-stage open project for an AI that translates between engineering
and legal language, flags domain false friends, and maps product
descriptions to the EU AI Act and GDPR, with sources.

## The problem

Engineers and lawyers often use the same words with different meanings.
"Model", "risk", "provider", "deployment" or "accuracy" can mean one thing
in a technical specification and another under the AI Act or GDPR. These
domain false friends cause misunderstandings in product reviews,
compliance assessments and contracts.

## What BridgeLLM aims to do

- Detect domain false friends between engineering and legal vocabulary
- Map product descriptions to relevant provisions of the EU AI Act and
  GDPR first, with US law to follow
- Cite sources for each mapping
- Generate questions a lawyer should ask, rather than give legal conclusions

## Current status

- A first-draft glossary book is ready, with its concept and structure
  defined
- This repository holds the structured glossary seed that BridgeLLM
  will build on (see Structure below)
- The AI system itself is planned, not yet built

## Structure

- `docs/glossary.csv` — glossary entries
- `docs/taxonomy.md` — category definitions
- `src/build_glossary.py` — script to generate structured output
- `data/terms/` — term-specific notes and source material

## Glossary scope

EU, French and US law; AI governance; digital rights; platform
accountability; liability and risk; privacy and data protection.

Categories include foundational AI concepts, model design and internals,
data terminology, evaluation and trustworthiness, AI risk and regulatory
classifications, market and value-chain actors, biometrics and synthetic
content, security threats, and engineering operations.

## Open call for peer review

I am looking for:

- Peer reviewers (legal, technical or both)
- NLP/LLM engineers and knowledge engineers
- Partners and sponsors

To get involved, use the **Research collaboration** option on my
[contact page](https://www.kimavocat.com/#contact).

## License

- **Code:** Apache License 2.0 — see [`LICENSE`](LICENSE).
- **Glossary content** (`docs/` and `data/terms/`): Creative Commons
  Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) — see
  [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md).
- **Glossary book:** the glossary book by Habbine Estelle KIM is a separate
  work and is not licensed under this repository. All rights reserved.

Commercial licences for the glossary content are available on request via
the [contact page](https://www.kimavocat.com/#contact).
