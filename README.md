# Agentic Claims Processing Platform

A modular, agent-based platform that ingests an insurance claim, extracts its
fields, compares them against a single master policy document (covering **5
claim types**) **and cross-validates them against a structured system of record**
(policy master table + claims history), then returns a decision:
**APPROVED / PARTIALLY_APPROVED / REJECTED / PENDING_INFORMATION / MANUAL_REVIEW**.

It is built so that **~60% of the codebase is generic, reusable tooling** you
can drop into other use cases (KYC, invoice approval, loan underwriting) just by
calling tools by name. The claims logic is a thin domain layer on top.

> Runs **out of the box with no API key** (deterministic offline fallback).
> Set `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`) to switch extraction/reasoning to
> a real LLM — the provider is auto-detected, with zero code changes elsewhere.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run over the bundled sample claims
python examples/run_pipeline.py

# Run one file
python examples/run_pipeline.py data/sample_claims/claim_health_01.txt

# Run the API
uvicorn api.main:app --reload
#   POST /claims/upload  (multipart file)
#   POST /claims/text    {"text": "..."}
#   GET  /tools          (lists the reusable toolbox)

# Tests
pytest -q
```

Minimal deps to just run the engine: `pip install pydantic PyYAML`.

---

## Architecture

```
                 ┌──────────────── core/  (REUSABLE ~60%) ────────────────┐
                 │  tools/        document_loader · retriever (RAG)        │
                 │                rules_engine · extractor · record_store   │
                 │                llm_client                                │
                 │  agents/       BaseAgent · Orchestrator                 │
                 │  registry      call any tool by name                    │
                 │  schemas/      Context (shared blackboard), ToolResult  │
                 └────────────────────────────────────────────────────────┘
                                        ▲ composes
                 ┌──────────────── domain/ (CLAIMS-SPECIFIC ~40%) ─────────┐
   upload ─▶ Intake ─▶ Extraction ─▶ Policy ─▶ Validation ─▶ Adjudication  │
                 │   each agent only reads/writes the shared Context       │
                 └────────────────────────────────────────────────────────┘
```

The pipeline is a sequence of single-responsibility agents that communicate only
through a shared `Context` "blackboard" — never by importing each other. Swapping,
reordering, or adding an agent is a local change.

### The 5 claims agents
| Agent | Reads | Writes | Reusable tools it uses |
|-------|-------|--------|------------------------|
| `IntakeAgent` | uploaded file | `claim_text`, type guess | `document_loader` |
| `ExtractionAgent` | `claim_text` | `extracted`, `completeness` | `extractor` |
| `PolicyAgent` | `claim_type`, `extracted` | `facts`, `policy_context` | `retriever` (RAG) |
| `ValidationAgent` | `facts`, `extracted` | authoritative `facts`, `validation` | `record_store` |
| `AdjudicationAgent` | `facts` | `adjudication`, `report` | `rules_engine` |

### Structured-data validation (system of record)
The `ValidationAgent` cross-checks the claim against structured tables in
`data/structured/` (swap these for your real DB by pointing `record_store` at it):

- **`policies.csv`** — policy master: holder/nominee names, product type, status,
  cover dates, sum insured, premium status.
- **`claims_history.csv`** — prior settled claims (for duplicate detection and
  remaining-limit calculation).

It produces authoritative facts that **override** the document/heuristic guesses:
`policy_exists`, `name_match`, `within_policy_period`, `policy_active`,
`product_matches`, `not_duplicate`, `remaining_limit`, and an effective
`coverage_limit` = `min(sum_insured, remaining_limit)`.

### Decision logic (in `AdjudicationAgent`)
1. Any **eligibility** hard-rule failure (excluded cause, lapsed policy, **not on
   record, outside cover period, duplicate**) → **REJECTED**
2. Else any **completeness** hard-rule failure (missing policy no./amount) → **PENDING**
3. Else any **review** flag (**name mismatch, product mismatch**) → **MANUAL_REVIEW**
4. Else amount over the effective limit → **PARTIALLY_APPROVED** (pay up to limit)
5. Else → **APPROVED**. Payout = `amount − deductible`, floored at 0.

---

## The single policy document + rules

- `data/policies/master_policy.md` — one human-readable document holding all
  **5 claim types** (Auto, Health, Travel, Property, Life): limits, exclusions,
  required docs, and adjudicator guidance. The `PolicyAgent` retrieves the right
  section via RAG.
- `config/rules.yaml` — the machine-readable config (limits, deductibles,
  exclusion keywords) plus the declarative rule definitions.

### Policy document is the source of truth (auto-compile)
Edit the document, then regenerate the config so decisions follow:

```bash
python examples/compile_policy.py --dry-run   # preview the diff, write nothing
python examples/compile_policy.py             # regenerate rules.yaml (backs up old)
```

`domain/policy_compiler.py` reads `master_policy.md`, extracts each section's
limit / deductible / exclusion keywords, and regenerates the `claim_types:` block
of `rules.yaml`. The `rules:` definitions are preserved. With `ANTHROPIC_API_KEY`
set it uses the LLM (robust to free-form wording); otherwise a deterministic
parser handles the numeric values and best-effort exclusion keywords. Example:
edit a deductible in the doc → recompile → the payout for that claim type changes.

> Note: a per-policy `sum_insured` in `data/structured/policies.csv` still caps an
> individual claim (the document limit is the product-level default; the system of
> record wins for a specific policy).

---

## Reusing the tools elsewhere (the whole point)

Every capability is a `BaseTool` registered by name. To use one in a totally
different project:

```python
from core.tools.registry import ToolRegistry
reg = ToolRegistry.default()

# Reuse the rules engine for a loan check — no claims code involved:
reg.call("rules_engine",
         facts={"score": 720, "min": 650},
         rules=[{"id": "credit_ok", "field": "score", "op": "gte",
                 "value": "$min", "severity": "hard", "message": "score too low"}])

# Reuse extraction for invoices, contracts, anything:
reg.call("extractor", text=open("invoice.txt").read(),
         schema={"vendor": "supplier name", "total": "invoice total as a number"})
```

**To build a new agentic workflow** (e.g. invoice approval): write new agents in
a new `domain/`-style package that compose the same tools, then wire them with
the generic `Orchestrator`. Core, tools, registry and orchestrator stay untouched.

```python
from core.agents.orchestrator import Orchestrator
pipeline = Orchestrator(agents=[MyIntake(), MyExtract(), MyDecide()])
result = pipeline.run()
```

### Add your own tool
```python
from core.tools.base_tool import BaseTool

class SentimentTool(BaseTool):
    name = "sentiment"
    description = "Score text sentiment from -1 to 1."
    def _run(self, text: str, **_):
        return {"score": ...}

reg.register(SentimentTool())          # now callable as reg.call("sentiment", text=...)
```

---

## Project layout
```
config/        settings.py · rules.yaml         # editable policy config + rules
core/          tools/ agents/ schemas/ utils/   # REUSABLE platform (~60%)
domain/        agents/ schemas/ prompts/        # claims-specific (~40%)
               policy_compiler.py               # policy doc -> rules.yaml
data/          policies/master_policy.md        # the single policy document
               structured/policies.csv          # policy master (system of record)
               structured/claims_history.csv     # prior claims (dupes + limits)
               sample_claims/                    # 8 demo claims
api/           main.py                          # FastAPI upload service
examples/      run_pipeline.py                  # CLI demo
tests/         rules engine · pipeline · validation
```

## Persistence (database)

Every processed claim and its decision is saved. The data layer is
**database-agnostic** (SQLAlchemy):

- **Local dev (default):** SQLite file `./claims.db` — no server, no Docker.
- **Postgres / Azure:** set `DATABASE_URL` and the same code uses it, e.g.
  `postgresql+psycopg2://USER:PASSWORD@HOST.postgres.database.azure.com:5432/DBNAME?sslmode=require`

```bash
python scripts/seed_db.py          # create tables + load policy master/history
python examples/save_and_list.py   # process samples, SAVE decisions, list them
```

Layout of the data layer:
```
db/        database.py (engine/session) · models.py (Claim/Policy/History) · repository.py
services/  claims_service.py   # runs the pipeline + persists (keeps domain/ DB-free)
scripts/   seed_db.py
```
The `domain/` pipeline stays free of any database concern; `services/ClaimsService`
is the only glue. Tables: `claims` (every decision, with full nested detail),
`policies` and `claims_history` (the system of record, seeded from the CSVs).

## Swapping in a real LLM (OpenAI or Anthropic)
```bash
cp .env.example .env
# then set ONE of:
#   OPENAI_API_KEY=sk-...        (model defaults to gpt-4o-mini; OPENAI_MODEL overrides)
#   ANTHROPIC_API_KEY=...        (model defaults to claude-sonnet-4-6)
```
`core/tools/llm_client.py` is multi-provider. It auto-detects the provider from
whichever key is present (OpenAI preferred if both are set), or you can force one
with `LLM_PROVIDER=openai|anthropic|offline`. With OpenAI it uses native JSON mode
for clean structured extraction. With no key it uses the offline heuristic so the
demo always runs. Every agent and tool calls the same `complete()` /
`extract_json()` interface, so switching providers needs **no code changes** —
and the policy compiler's exclusion extraction is sharpest with a real key.
```
