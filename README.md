# Financial Twin — KBC Hackathon PoC

> A working prototype. `docker compose up --build`, then open <http://localhost:3000>.
> No API key required. All data is synthetic.

---

## What it is

A Financial Twin is one living, explainable model of a customer's financial life —
life phase, household, goals, trajectory, risks and intent — with a confidence
level and a reason attached to every single conclusion. Every KBC channel reads
and writes that same Twin through one API instead of each guessing
independently. The customer can see the Twin, understand why it says what it
says, and correct it — and their correction outranks the machine, permanently
and everywhere. It is deliberately boring underneath: streaming rules and
arithmetic do the work, and an LLM is used only to choose words. Success is
measured as **the customer's progress toward their own goals**, not sales.

## Why it matters

Today the app knows transactions, the advisor knows conversations, insurance
knows policies, and Kate knows questions. Four partial pictures of one person,
each maintaining its own personalisation logic, each drifting from the others.

**Instead of every channel guessing independently who the customer is, KBC
maintains one transparent, customer-owned financial model.**

That flips personalisation from a feature each channel builds to an asset the
bank owns — and, because the customer can inspect and correct it, from
something done *to* them into something they participate in.

---

## Run

```bash
docker compose up --build
```

| | |
|---|---|
| **Demo** | <http://localhost:3000> |
| **Twin API** | <http://localhost:8000/api/health> |
| **API docs** | <http://localhost:8000/docs> (also proxied at `/docs`) |

First boot takes ~15 seconds: it generates 1,000 customers with 12 months of
transactions (~180,000 rows) and then runs the scale benchmark in a background
thread. The frontend shows a loading state until the API answers.

**No Docker?**

```bash
./run.sh          # same two URLs, venv + stdlib http server with an /api proxy
```

**Optional — turn on Claude for the narrative wording:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # then docker compose up --build
```

Everything works identically without it. See
[Why not call the LLM for every transaction?](#why-not-call-the-llm-for-every-transaction)

---

## Demo personas

Three hand-built customers whose "before" state is deliberately chosen so that
one injected event produces a visible, meaningful change.

### A — Lotte Vermeulen, 23, Leuven — *First job*

A student who just graduated. Ten months of student income and parental
transfers, then **one** salary payment last month.

Her Twin reads **"Studying", 97% confident** — correctly, because one salary
payment is not a pattern. `salary_months_consecutive` is 1, so `salary_detected`
is false.

**Inject first salary** → two consecutive employer payments → `salary_detected`
flips → life phase becomes **"Starting career", 91% confident**, the emergency
fund target recalculates against her new income, and "First recurring salary"
appears on the Future Me timeline (it was correctly absent before — you cannot
call something recurring on one occurrence).

### B — An De Smet, 31, Gent — *Possible family expansion*

A couple renting in Gent. The last three months contain baby-shop purchases
(€78) and prenatal care (€52).

Family expansion sits at **45% — deliberately below the 50% threshold**. Buying
baby things is not evidence of a baby; it could be a gift, a niece, a friend's
shower. The signal is visible in the app as an open question, and nothing acts
on it.

**Inject crib purchase** (€620 of nursery furniture) → **78%**. Nursery
furniture is different in kind: it is a thing you buy for a room in your own
home. Now the playbook activates — and the wording stays honest:

> "Some recent spending looks like preparing for a baby — we are 78% confident,
> which means we are not sure. We have not told anyone anything, and you can
> correct this."

The advisor view says, in as many words: **do not congratulate, do not raise it
unprompted.**

Then **correct it** ("That's not right") → the signal is marked
`suppressed_by_customer`, the playbook disappears, the childcare costs come off
the projection, and the advisor view shows the correction as a declared fact.

### C — Marc Peeters, 58, Mechelen — *Nearing pension*

31 years at the same employer, €4,100/month, mortgage nearly repaid, €68,000
saved, €585/month going into savings, investments and pension saving.

His projection: target income €3,075/month, estimated state pension
€1,640/month, a **€1,435/month gap**, €344,400 of capital needed against
€121,680 projected — a **€222,720 shortfall**, 35% ready. Retirement age 65 is
**our assumption**, clearly labelled, and changing it rewrites the projection.

- **Inject €3,000 expense** → the shortfall grows by exactly €3,000 and the
  capital *needed* does not move. A new kitchen is not a permanent change to
  your cost of living, and a model that let it inflate his retirement target
  would be wrong. (There is a test for this.)
- **Inject €500 to savings** → contribution rate rises, projected capital rises,
  shortfall falls.

---

## Demo actions

Four buttons in the right-hand panel. Each publishes **one** transaction onto
the event queue; the API returns immediately with an `event_id`, and the UI
polls while the worker processes it asynchronously. The pipeline card animates
through the real stages and then shows the **measured** per-stage timings.

| Button | What to watch |
|---|---|
| Inject first salary | Life phase flips; the timeline gains a milestone |
| Inject crib purchase | Confidence 45% → 78%, and it stays an assumption |
| Inject €3,000 expense | Pension shortfall moves; the target does not |
| Inject €500 to savings | Projected dates move earlier |

Plus: **Edit my Twin** (bottom sheet — life phase, house plans, family,
retirement age, goal targets) and **Reset the demo**.

---

## Architecture

```
  Transactions / KBC Mobile / Kate / Advisor / Insurance / Lending
                              |
                              v
                       Event ingestion            asyncio.Queue  ->  Kafka
                              |
                              v
                  TIER 1  Streaming features      app/features.py
                              |
                              v
                  TIER 2  Life-event scoring      app/scoring.py
                              |
                              v
                     THE FINANCIAL TWIN           app/twin_engine.py
                              |
                              v
                      Shared Twin API             app/main.py
                       /      |      \
              Customer app   Kate   Advisor
                              |
                              v
                  TIER 3  Narrative wording       app/llm.py
```

### Tier 1 — streaming feature updates

One function, `apply_transaction(state, txn)`, folds a transaction into a
per-customer feature state (~56 features: income, salary detection, savings
rate, rent, mortgage, recurring costs, childcare, baby-related spend,
emergency-fund months, trends, …).

That same function is used by **all three** entry points — the 12-month history
replay at seed time, the live event queue, and the benchmark. Using one code
path is deliberate: batch/stream drift is the most common failure mode of real
feature pipelines, and here it is structurally impossible.

### Tier 2 — interpretable scoring

13 scoring models (11 behavioural signals + 7 life-phase candidates). Each is a
list of weighted rules; a rule that fires contributes its weight **and a
human-readable piece of evidence**. The score is the clamped sum.

These are **not** machine learning, and the code says so. They are
*interpretable scoring models*, chosen because:

- every output is explainable **by construction** — the evidence list *is* the
  model, so "why we think this" needs no post-hoc interpretation layer;
- thresholds are visible and tunable in one dict (`scoring.THRESHOLDS`);
- behaviour is deterministic, so the demo and the tests agree.

The interface (`id, score, evidence`) is what a trained model would also expose,
so swapping any single model for a real classifier is local work.

Three design features worth calling out:

- **Applicability gates.** A model can declare that it *does not apply* — which
  is different from "applies but scored low". Without this, "saving for a first
  home" fires for people who already own one, because the savings rules are
  blind to the mortgage.
- **A hard confidence ceiling.** `MAX_INFERRED_CONFIDENCE = 0.97`. An inference
  can never reach certainty. Only a customer correction gets 1.0.
- **Per-model ceilings.** Intent models cap at 0.80. We can be nearly certain
  about an observed *pattern*; never about what someone privately *plans*.

### Tier 3 — narrative generation

Claude writes two or three sentences of plain language from an
already-computed summary. It never calculates, projects or decides anything.
Without `ANTHROPIC_API_KEY`, a deterministic template runs instead — not a stub,
but the fallback a bank would actually ship.

---

## Production mapping

```
asyncio.Queue              ->  Kafka, partitioned by customer_id
single Python worker       ->  Flink / Kafka Streams, one operator per partition
SQLite features table      ->  online feature store (low-latency K/V)
SQLite twins table         ->  operational store + a Twin-change topic
single FastAPI process     ->  horizontally scaled Twin Service
pipeline_trace table       ->  platform tracing, metrics and audit log
```

**Why this scales:** events are partitioned by customer, so the per-customer
path is **single-writer and ordered** — no locks, no coordination. That property
is already true in the prototype; the production version changes the transport,
not the shape.

---

## Why not call the LLM for every transaction?

Four reasons, in order of how much they matter to a bank:

1. **Consistency.** If the model computes the numbers, two channels asking the
   same question at the same moment can get different answers. The Twin is one
   deterministic document; the LLM only reads it.
2. **Auditability.** "Why did the customer see this?" must be answerable years
   later. A rule with weights and evidence can be replayed exactly. A
   generation cannot.
3. **Cost.** At 2.3M customers and ~45 transactions each per month, per-transaction
   generation is **103.5M calls/month**. Calling only on meaningful Twin change
   or app open is **3.68M** — **28× fewer**, for the same customers.
4. **Latency.** Tier 1 + Tier 2 run in ~6 µs per event. A network round-trip to
   a model is four orders of magnitude slower and cannot sit in a
   transaction path.

The rule the code enforces: **deterministic state first, LLM second.** Financial
calculation belongs in code. The LLM chooses words.

---

## Privacy

This prototype is **entirely synthetic** — 1,000 generated customers, Faker
`nl_BE` names, and real Belgian merchant names used only as realistic labels. No
KBC customer data is involved. It makes **no claim of regulatory compliance**.

> A production version would need to be designed and validated against KBC's
> legal, risk, security and GDPR requirements.

The thing this prototype *does* demonstrate is the data model a compliant
version would need. Every value in the Twin carries one of four provenance
labels, and the UI renders that label everywhere:

| | |
|---|---|
| **observed** | It happened. A transaction, a balance. Verifiable. |
| **derived** | Arithmetic on observed data. Reproducible, not a judgement. |
| **inferred** | A probabilistic conclusion. May be wrong. |
| **declared** | The customer told us. Outranks everything above. |

**An inference is never presented as a fact.** Confidence is rendered as a
segmented meter rather than a bar (a probability is not a quantity of
something), uncertain milestones are drawn with dashed markers, and signals
below their threshold are shown but not acted on.

For production, the open questions this prototype deliberately surfaces rather
than solves: GDPR and purpose limitation, consent for sensitive-adjacent
inference (family expansion, health), data minimisation, explainability,
correction rights, audit trails, sensitive-inference controls, human oversight,
model governance, and security boundaries between channels.

---

## Scaling

**Measured** on this machine (Docker, Linux aarch64, Python 3.12, 8 cores), by
`app/benchmark.py` at startup — the UI reads these from `/api/benchmark`, it
does not hardcode them:

```
100,000 customers
1,200,000 events
6.8 s wall
176,497 events / second
5.67 µs average per event
0.064 / 0.080 / 0.098 ms  p50 / p95 / p99 per customer
```

One run, on one machine. Repeat runs on the same box land between roughly
**176k and 181k events/second** — it is a measurement, so it moves. The
Architecture & Scale page always shows the figures from the run that actually
happened on your machine, and the "Re-run the benchmark" button re-measures
live. Peak RSS is reported too, but it is a process-wide high-water mark that
includes seeding, so treat it as an upper bound rather than the engine's
footprint.

**Timed:** Tier 1 feature updates, Tier 1 derived features, Tier 2 scoring
across all models.
**Not timed:** SQLite writes, HTTP, Tier 3. Storage and transport are exactly
what production replaces (Kafka + a feature store), so timing SQLite would
measure the wrong thing.

**Extrapolation — arithmetic, not a measurement:**

```
2.3M customers  ~=  27.6M equivalent events
                    2.6 min   on one worker, one core
                    7.8 s     on 20 parallel workers (theoretical)
```

Caveats we are not hiding: one Python process, one core, no network, no durable
writes. Production adds Kafka, a feature store and replication, so real
throughput per worker will be lower — but it scales out across partitions,
because the per-customer path is single-writer.

Re-run it yourself:

```bash
python scripts/benchmark.py --customers 250000 --events 12
```

### Cost

All inputs are configurable in `.env.example` — none of this is a price quote.

| Assumption | Value |
|---|---|
| Population | 2,300,000 |
| Open the app daily | 5% |
| Meaningful Twin change per month | 10% |
| Tokens per call (in / out) | 900 / 160 |
| Price per MTok (in / out) | $4.00 / $20.00 |

| | Calls / month | Cost / month |
|---|---|---|
| **Selective** (Twin change or app open) | 3,680,000 | ~$25,000 |
| Per transaction (what we avoid) | 103,500,000 | ~$704,000 |
| | **28× fewer** | |

The deterministic core absorbs all 103.5M monthly events in **~0.16 single-worker
CPU-hours** — commodity compute, not model inference. Storage is a Twin document
plus an append-only version history per customer: kilobytes each, dwarfed by the
transaction history that already exists.

> Prices are configurable values, not quoted contract prices. Verify against
> current Anthropic pricing before using any of this in a business case.

---

## Tests

```bash
cd backend && python -m pytest          # 27 tests
./scripts/smoke_test.sh                 # 17 checks against a running stack
```

The five required flows, plus the invariants that hold the architecture
together:

| Test | Asserts |
|---|---|
| 1 — inject salary | Salary feature updates, first-job score rises, phase changes, timeline gains the milestone |
| 2 — inject crib | Baby signal rises past threshold **and** uncertainty stays explicit, advisor is told not to congratulate |
| 3 — correction | Stored, persisted, and house recommendations suppressed in goals, timeline **and** the advisor view |
| 4 — same Twin | Customer and advisor endpoints return the same version, including after an event from a different channel |
| 5 — no API key | Template fallback produces a real narrative, quoting numbers the engine computed |

Plus: provenance is present and valid on every field; no inference reaches
certainty; a one-off expense does not change the retirement *target*; extra
saving improves the projection; savings transfers are not counted as spending;
goals never double-count the same euro; the pipeline is asynchronous and traced;
Twin history is append-only; benchmark figures scale with the workload (proving
they are measured); playbooks contain no sales language.

---

## Repository

```
financial-twin/
├── docker-compose.yml          two services, no Kafka/Redis/Postgres
├── run.sh                      Docker-free fallback, same two URLs
├── .env.example                every knob, all optional
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             the one shared Twin API
│   │   ├── db.py               stdlib sqlite3, ~120 lines, no ORM
│   │   ├── schemas.py          the Twin data model (provenance everywhere)
│   │   ├── catalog.py          Belgian merchants and categories
│   │   ├── personas.py         the three hero personas, hand-built
│   │   ├── seed.py             1,000 customers x 12 months, fixed seed
│   │   ├── event_bus.py        TIER 1 transport: asyncio.Queue + worker
│   │   ├── features.py         TIER 1 feature updates
│   │   ├── scoring.py          TIER 2 interpretable models + thresholds
│   │   ├── playbooks.py        13 life-moment playbooks
│   │   ├── twin_engine.py      deterministic assembly, corrections, projections
│   │   ├── llm.py              TIER 3, Claude or template
│   │   └── benchmark.py        measured throughput + cost model
│   └── tests/test_flows.py     27 tests
├── frontend/                   no build step: plain ES modules + nginx
│   ├── Dockerfile
│   ├── nginx.conf              serves the app, proxies /api -> backend
│   ├── index.html
│   └── src/
│       ├── styles/tokens.css   KBC design tokens (see below)
│       ├── styles/app.css      component layer, tokens only
│       ├── components.js       the KBC component system
│       ├── api.js, format.js
│       └── views/              customer.js, advisor.js, architecture.js
└── scripts/
    ├── benchmark.py            standalone, no API needed
    └── smoke_test.sh           17 end-to-end checks
```

### A note on the frontend

No npm, no bundler, no `node_modules` — plain ES modules served by nginx, which
also proxies `/api` to the backend so there is one origin, no CORS, and one URL
to remember.

The design tokens are not improvised. They were taken from KBC's own published
design-language file:

```
https://wcmassets.kbc.be/etc.clientlibs/kbc/components/kdl-design-tokens.latest.min.css
https://wcmassets.kbc.be/etc.clientlibs/kbc/components/websites/cta-button.min.css
```

| Token | Value | KDL name |
|---|---|---|
| Primary (navy) | `#0D2A50` | `--kdl-color-primary-main` |
| Accent (KBC blue) | `#0097DB` | `--kdl-color-primary-accent` |
| Dashboard background | `#F2FAFF` | `--kdl-color-func-background-dashboard` |
| Text secondary / border | `#45658F` / `#BFDAFF` | `--kdl-color-func-text-light` / `-border` |
| Success / warning / error | `#5BA215` / `#DC7507` / `#D64040` | `--kdl-color-system-*` |
| Channel colours | Kate `#55C7DF`, Mobile `#1FADC1`, Live `#1DA594` | `--kdl-color-os-*` |
| Buttons | pill `100px`, min-height `40px`, padding `7px 24px`, weight 500 | from `cta-button.min.css` |
| Card shadow | `0 4px 16px rgba(0,54,101,.08)` | from the implemented site CSS |

KBC ships **MuseoSans** (weights 300/500/700), which is licensed. It is first in
the font stack — so it renders natively on a KBC machine — with **Mulish** (the
closest open geometric-humanist sans) loaded as the substitute.

No KBC logo, illustration or proprietary icon is reproduced. The wordmark is
text, the icons are neutral inline SVG, and the prototype labels itself as a
prototype.

---

## Limitations

Being explicit, because a jury will find these anyway:

- **The scoring models are rules, not ML.** Deliberately, and the code calls
  them "interpretable scoring models" rather than dressing them up. Real models
  would need labelled life-event data KBC has and this prototype does not.
- **Thresholds are hand-tuned** against synthetic data whose generator I also
  wrote. That is circular; real thresholds need real outcome data.
- **The retirement projection is simplified**: 75% income replacement, a 40%
  statutory estimate capped at €2,000/month, 20 years of retirement, and **no
  investment return**. Every one of those is surfaced in the UI as an
  assumption. It is not financial advice.
- **The benchmark measures the engine, not a system.** No network, no durable
  writes, no serialisation. The extrapolation is honest arithmetic on that
  number and is labelled as an estimate everywhere it appears.
- **SQLite single-writer** is fine for one demo box and would be the first thing
  to go.
- **No authentication, no authorisation, no channel identity.** Every endpoint
  is open. A real Twin API needs per-field authorisation per channel.
- **The household model is thin** — one customer, an optional partner name. Real
  joint finances (two account holders, one Twin) is a genuine design problem
  this prototype gestures at rather than solves.
- **Corrections are last-write-wins** with no expiry. "I'm not buying a house"
  should probably lapse after a year; here it is forever.
- **Tier 3 is untested against the live API in this build** — the Claude path is
  implemented and fails safe to the template, but the demo was verified without
  a key.

---

## The 3-minute jury pitch

> **Today, every KBC channel knows a piece of the customer.**
>
> The app knows transactions. The advisor knows conversations. Insurance knows
> policies. Kate knows questions.
>
> But the customer is one person.
>
> **Financial Twin gives KBC one shared, living understanding of where that
> customer is going financially.**
>
> This is Lotte. She's 23, she just graduated, and her Twin says "Studying" —
> 97% confident. That's correct: she's had exactly one salary payment, and one
> payment is not a pattern.
>
> *[Click "Inject first salary"]*
>
> One transaction goes onto the event queue. The API returns immediately.
> Watch it move: Tier 1 updates her features, Tier 2 re-scores thirteen models,
> and the Twin writes a new version. Six milliseconds, end to end — and the
> timings on screen are the real ones from that event.
>
> She's now "Starting career", 91% confident — **and it tells you why**: a
> second consecutive salary from the same employer, a 117% income increase, a
> previous student-income history. Her Future Me timeline just gained a
> milestone that wasn't there before, because now it's genuinely recurring.
>
> *[Switch to Advisor View]*
>
> The advisor already sees it. Same version number. **Not a copy — the same
> document, from the same API.** There is no advisor-side personalisation logic
> in this codebase at all.
>
> *[Switch to An]*
>
> An's spending shows baby-shop purchases and prenatal care. We sit at 45% —
> below our threshold — because buying baby things is not evidence of a baby.
>
> *[Click "Inject crib purchase"]*
>
> 78%. And we say exactly that: "we are 78% confident, which means we are not
> sure." The advisor view says: do not congratulate. Do not raise it unprompted.
>
> *[Click "That's not right"]*
>
> And she can tell us we're wrong. That correction outranks the machine — the
> signal is switched off, the playbook disappears, the childcare costs come off
> her projection, everywhere, permanently. **The customer owns the model.**
>
> *[Switch to Architecture & Scale]*
>
> We measured it: 100,000 customers, 1.2 million events, **176,000 events per
> second**. Extrapolated — and we label it an estimate — 2.3 million customers is
> 2.6 minutes on one worker, under eight seconds on twenty.
>
> The LLM never touches that path. It writes two sentences when the Twin
> changes, or when you open the app. That's 28× fewer calls than generating per
> transaction, for the same customers.
>
> **The opportunity is not to make every KBC channel smarter independently. It
> is to give every channel the same understanding of the customer — and let the
> customer own that understanding.**

---

## "Why does this need AI?" — the jury question

**AI is not the core database, and it is not doing the maths.**

The value is in continuously converting fragmented behavioural signals into an
explainable shared customer model. Most of that is rules and streaming, because
most of it *should* be: it runs on every transaction, it has to be auditable,
and it has to be identical across channels. That is 100% of the 103.5M monthly
events, handled deterministically at 176,000 events/second.

AI is used **selectively, where it genuinely adds value**:

- **Interpretation** — turning "salary_months_consecutive went 1 → 2 and income
  rose 117%" into a conclusion a human recognises as *starting a career*. The
  rules do this today; individual models can become trained classifiers behind
  the same `(score, evidence)` interface, without changing anything downstream.
- **Communication** — turning a finished Twin into two sentences that sound like
  a person wrote them. That is the part a bank genuinely cannot do well with
  templates at 2.3M-customer scale and 2,300 distinct financial situations.

And critically: **the Twin stays auditable and customer-controlled.** Because
the LLM cannot compute, there is no scenario where a generated number reaches a
customer. Because every field carries its provenance and evidence, any
conclusion can be replayed years later. Because the customer can correct it, the
model is accountable to the person it describes.

That is the part that is hard to buy, and the part that compounds.
