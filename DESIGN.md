# Agentic Claims Processing Platform — System Design

**Version:** 1.0 · **Status:** Working prototype (engine + persistence done; API/UI/deploy in progress)
**Stack:** Python · FastAPI · SQLAlchemy · Postgres · React (planned) · OpenAI/Anthropic · Docker/Azure (planned)

---

## 1. What this is

An agentic platform that ingests an insurance claim (file upload), **extracts** its
fields, **compares** them against a single master policy document (5 claim types),
**cross-validates** them against a structured system of record (policy master +
claims history), and returns a decision — **APPROVED / PARTIALLY_APPROVED /
REJECTED / PENDING_INFORMATION / MANUAL_REVIEW** — with reasons, payout and an
audit trail. Every decision is **persisted** to a database.

It is deliberately built so the engine (~60% of the code) is **generic and
reusable**: the same agents, tools, registry and orchestrator can power other
document → extract → validate → decide workflows (invoice approval, KYC, loan
underwriting) by swapping the thin domain layer.

---

## 2. Design principles

1. **Modular, layered, decoupled.** A reusable *core* (agents/tools/orchestrator),
   a claims-specific *domain* layer on top, and *infrastructure* (db, api, ui)
   around the edges. Agents never import each other — they share a `Context`.
2. **Everything is a tool, callable by name.** Capabilities (load, extract,
   retrieve, validate against records, evaluate rules) are registered in a
   `ToolRegistry` and invoked via `registry.call("name", ...)`.
3. **Provider-agnostic LLM.** OpenAI or Anthropic, auto-detected from env, with a
   deterministic offline fallback so it runs with no key.
4. **Database-agnostic.** SQLAlchemy: SQLite locally, Postgres (Azure) in prod —
   one env var, no code change.
5. **Policy document is the source of truth.** A compiler turns the human-readable
   policy doc into the machine-readable rules config.
6. **Runs out of the box.** No key, no DB server, no Docker required to see it work.

---

## 3. Architecture (layers)

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION            React frontend (planned)  ── HTTP/JSON ──┐    │
├──────────────────────────────────────────────────────────────────┼────┤
│  INTERFACE / API         FastAPI  (api/main.py)                   │    │
│                          POST /claims · GET /claims · GET /claims/{id} │
├──────────────────────────────────────────────────────────────────┼────┤
│  SERVICE                 services/ClaimsService                   │    │
│                          (runs pipeline + persists)               │    │
├───────────────────────────────────────────┬──────────────────────┼────┤
│  DOMAIN (claims-specific ~40%)             │  PERSISTENCE          │    │
│  Orchestrated agent pipeline:              │  db/ (SQLAlchemy)     │    │
│   Intake→Extraction→Policy→Validation→     │   claims              │    │
│   Adjudication                             │   policies            │    │
│  + policy_compiler (doc→rules)             │   claims_history      │    │
├───────────────────────────────────────────┴──────────────────────┤    │
│  CORE (reusable ~60%)                                             │    │
│   agents:  BaseAgent · Orchestrator                              │    │
│   tools:   document_loader · extractor · retriever(RAG) ·        │    │
│            record_store · rules_engine · llm_client              │    │
│   registry · schemas(Context) · utils(matching, logger)         │    │
├──────────────────────────────────────────────────────────────────┤    │
│  EXTERNAL    LLM (OpenAI/Anthropic) · Postgres · (Redis/Blob planned) │
└──────────────────────────────────────────────────────────────────────┘
```

**Why this shape:** each layer depends only on the one below it. The domain layer
composes core tools; the service layer glues domain + persistence; the API exposes
the service; the UI calls the API. You can replace any layer (UI framework, DB,
LLM) without touching the others.

---

## 4. The decision pipeline (data flow)

A claim flows through five single-responsibility agents that read from and write to
a shared `Context` "blackboard":

| # | Agent | Does | Reusable tool used |
|---|-------|------|--------------------|
| 1 | **Intake** | load uploaded file → text; first-pass claim-type guess | `document_loader` |
| 2 | **Extraction** | text → structured fields (name, policy no., amount…) | `extractor` (LLM/JSON) |
| 3 | **Policy** | retrieve the right policy section; load type config | `retriever` (RAG) |
| 4 | **Validation** | cross-check vs system of record (exists? active? duplicate? remaining limit?) | `record_store` |
| 5 | **Adjudication** | run declarative rules → decision + payout + reasons | `rules_engine` |

**Decision logic (deterministic, in Adjudication):**
1. Any *eligibility* hard failure (excluded cause, lapsed policy, not on record,
   outside cover period, duplicate) → **REJECTED**
2. Else any *completeness* hard failure (missing policy no./amount) → **PENDING**
3. Else any *review* flag (name/product mismatch) → **MANUAL_REVIEW**
4. Else amount over effective limit → **PARTIALLY_APPROVED** (pay up to limit)
5. Else → **APPROVED**. Payout = `amount − deductible`, floored at 0.

The *effective limit* = `min(product limit from policy doc, policy sum_insured,
remaining limit after prior claims)` — i.e. structured data can tighten the payout.

---

## 5. Component catalog

### Core — reusable (`core/`)
| Module | Responsibility |
|--------|----------------|
| `schemas/base.py` | `Context` (shared blackboard), `ToolResult`, `AgentResult`, timing |
| `tools/base_tool.py` | abstract `Tool` with uniform `run()` + error guard + LLM-spec |
| `tools/registry.py` | register/lookup/call tools by name; `default()` factory |
| `tools/document_loader.py` | file (txt/md/pdf/docx) → text |
| `tools/extractor.py` | text + schema → structured dict (LLM with offline fallback) |
| `tools/retriever.py` | dependency-free RAG: chunk + score + return top-k |
| `tools/record_store.py` | structured lookup over CSV/JSON (policy master, history) |
| `tools/rules_engine.py` | evaluate declarative rules (eq/gte/in/regex/between…) |
| `tools/llm_client.py` | multi-provider LLM (OpenAI/Anthropic/offline), JSON mode |
| `agents/base_agent.py` | agent lifecycle: timing, logging, error capture |
| `agents/orchestrator.py` | generic sequential pipeline runner |
| `utils/matching.py` | fuzzy name match, lenient date parse, number coercion |

### Domain — claims-specific (`domain/`)
| Module | Responsibility |
|--------|----------------|
| `agents/intake_agent.py` | load + classify claim type |
| `agents/extraction_agent.py` | extract & normalise claim fields |
| `agents/policy_agent.py` | RAG over master policy; inject per-type config |
| `agents/validation_agent.py` | cross-check vs system of record |
| `agents/adjudication_agent.py` | rules → decision + payout + citations |
| `agents/claims_orchestrator.py` | wires the 5 agents into `ClaimsPipeline` |
| `policy_compiler.py` | master_policy.md → rules.yaml (LLM + offline) |
| `schemas/claim.py` | `ExtractedClaim`, `Adjudication`, `ClaimDecisionReport` |
| `prompts/templates.py` | extraction schema + claim-type keyword hints |

### Config / data
| Path | Responsibility |
|------|----------------|
| `config/settings.py` | paths, env config |
| `config/rules.yaml` | per-type limits/deductibles/exclusions + rule definitions |
| `data/policies/master_policy.md` | **single** policy doc, all 5 claim types |
| `data/structured/policies.csv` | policy master (system of record) |
| `data/structured/claims_history.csv` | prior claims (dupes + remaining limit) |

### Infrastructure
| Path | Responsibility | Status |
|------|----------------|--------|
| `db/database.py` `models.py` `repository.py` | SQLAlchemy engine, tables, CRUD | ✅ done |
| `services/claims_service.py` | pipeline + persistence glue | ✅ done |
| `scripts/seed_db.py` | create tables + seed structured data | ✅ done |
| `api/main.py` | FastAPI endpoints | 🟡 skeleton → Stage 2 |

---

## 6. Target deployment architecture (Azure mapping)

Mapping to the reference Azure topology you shared:

| Azure component | Role | This project | Status |
|-----------------|------|--------------|--------|
| Postgres flexible server | database | `db/` (SQLAlchemy, Postgres-ready) | ✅ done |
| Container App Job (seed) | one-off seeding | `scripts/seed_db.py` | ✅ done |
| `*-backend` Container App | API | `api/` (FastAPI) | 🟡 Stage 2 |
| `*-frontend` Container App | web UI | `frontend/` (React) | ⬜ Stage 3–4 |
| `*-worker` Container App | async processing | Celery/RQ worker | ⬜ later |
| `*-beat` Container App | scheduled jobs | Celery beat | ⬜ later |
| Redis | queue broker + cache | Redis | ⬜ later |
| Storage account | durable uploaded files | Azure Blob | ⬜ Stage 5 |
| Container registry | Docker images | ACR + Dockerfiles | ⬜ Stage 5 |
| Container Apps Environment | hosting wrapper | Bicep/IaC | ⬜ Stage 5 |

**Async note:** today the pipeline runs *inline* (request waits for the result),
which is fine for low volume. Worker + beat + redis become valuable at scale or
with slow LLM calls — they let an upload return instantly while processing happens
in the background, plus scheduled jobs (nightly reports, retry pending claims).

---

## 7. Folder structure (current + planned)

```
agentic-claims-platform/
├── core/                      # REUSABLE engine (~60%)
│   ├── agents/                #   BaseAgent, Orchestrator
│   ├── tools/                 #   document_loader, extractor, retriever,
│   │                          #   record_store, rules_engine, llm_client, registry
│   ├── schemas/               #   Context, ToolResult, AgentResult
│   └── utils/                 #   matching, logger
├── domain/                    # CLAIMS-SPECIFIC (~40%)
│   ├── agents/                #   intake, extraction, policy, validation,
│   │                          #   adjudication, claims_orchestrator
│   ├── schemas/  prompts/
│   └── policy_compiler.py     #   policy doc -> rules.yaml
├── config/                    # settings.py, rules.yaml
├── data/
│   ├── policies/master_policy.md       # the single policy document
│   └── structured/                     # policies.csv, claims_history.csv (system of record)
├── db/                        # ✅ SQLAlchemy: database, models, repository
├── services/                  # ✅ ClaimsService (pipeline + persistence)
├── scripts/                   # ✅ seed_db.py
├── api/                       # 🟡 FastAPI backend  (Stage 2)
├── frontend/                  # ⬜ React app        (Stage 3–4)
├── storage/                   # ⬜ blob abstraction (Stage 5)
├── worker/                    # ⬜ async tasks      (later)
├── migrations/                # ⬜ Alembic          (later)
├── deploy/                    # ⬜ Dockerfiles, compose, Azure IaC (Stage 5)
├── examples/                  # run_pipeline, compile_policy, save_and_list
└── tests/                     # 31 tests (rules, pipeline, validation, compiler, llm, persistence)
```

---

## 8. Reusability (the cross-use-case angle)

Every capability is a named tool, so a different workflow reuses them directly:

```python
from core.tools.registry import ToolRegistry
reg = ToolRegistry.default()

# rules engine for a loan check — no claims code:
reg.call("rules_engine", facts={"score": 720, "min": 650},
         rules=[{"id":"credit_ok","field":"score","op":"gte","value":"$min",
                 "severity":"hard","message":"score too low"}])

# extraction for invoices/contracts — just a different schema:
reg.call("extractor", text=open("invoice.txt").read(),
         schema={"vendor":"supplier name","total":"invoice total as a number"})
```

A new agentic workflow = new agents that compose the same tools + a 5-line
`Orchestrator([...])`. Core, tools, registry and orchestrator stay untouched.

---

## 9. Roadmap (staged, each stage runnable)

| Stage | Scope | Status |
|-------|-------|--------|
| 0 | Engine: agents, tools, 5-type adjudication, policy doc + rules | ✅ done |
| 0.5 | Structured-data validation (record_store + ValidationAgent) | ✅ done |
| 0.6 | Policy compiler (doc → rules) | ✅ done |
| 0.7 | Multi-provider LLM (OpenAI + Anthropic + offline) | ✅ done |
| **1** | **Persistence (SQLAlchemy, Postgres-ready): save/list/get** | ✅ **done** |
| **2** | **API: POST/GET /claims, /docs** | 🟡 next |
| 3 | Install Node + scaffold React frontend | ⬜ |
| 4 | Frontend UI: upload → decision view → dashboard | ⬜ |
| 5 | Dockerfiles + compose + blob storage + Azure deploy | ⬜ |
| 6 | Async layer: Redis + worker + beat | ⬜ |
| 7 | Auth/users + Alembic migrations | ⬜ |

---

## 10. Tech stack

- **Language:** Python 3.9+
- **API:** FastAPI + Uvicorn
- **Data:** SQLAlchemy 2.0 (SQLite dev / Postgres prod), Pydantic 2
- **LLM:** OpenAI (`gpt-4o-mini` default) or Anthropic (`claude-sonnet-4-6`), offline fallback
- **RAG/rules:** dependency-free keyword retriever + declarative YAML rule engine
- **Frontend (planned):** React + Vite
- **Deploy (planned):** Docker, Azure Container Apps, Azure Postgres, Blob, Redis
- **Testing:** pytest (31 tests, runs with no key/DB server)

---

## 11. Honest gaps (not built yet)

- **No auth / RBAC** — anyone hitting the API can process/read claims.
- **No DB migrations** — schema changes currently need a recreate (add Alembic).
- **Uploaded files aren't durable** — saved to local `uploads/`; need blob storage.
- **Inline processing only** — no async worker/queue yet (fine for low volume).
- **Extraction accuracy unbenchmarked** on real, messy documents (scanned PDFs,
  handwriting). Offline mode is heuristic; a real LLM key is recommended.
- **Policy/rules/data are illustrative**, not a real insurer's validated wordings.
- **No observability** (metrics/tracing) or rate limiting yet.

These are the difference between "working prototype" and "production system" — all
are additive on top of the current modular base, not rewrites.

---

## 12. Extension points (where to plug new things)

- **New claim type:** add a section to `master_policy.md`, run the compiler, add
  keyword hints + section map (one line each).
- **New decision rule:** add a rule dict to `config/rules.yaml` (+ a derived fact
  if needed) — no code for value/exclusion changes.
- **New data source for validation:** implement a tool with the `record_store`
  contract (e.g. a Postgres-backed lookup) and register it.
- **New LLM provider:** add a `_complete_<provider>` branch in `llm_client.py`.
- **New workflow (non-claims):** new agents composing existing tools + a new
  `Orchestrator` list.
