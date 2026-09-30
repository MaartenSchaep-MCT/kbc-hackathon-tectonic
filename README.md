# KBC Future Me

Meet Sarah. She's 29, just started a new job, and she and her partner want to
buy a house someday.

Today, KBC Mobile tells Sarah what already happened: what she spent last month,
which subscriptions she pays, a duplicate payment Kate caught. That's useful, but
it only looks backwards.

Sarah's real questions are about what's ahead. When can we buy a house? Can we
afford a second child? Will I be okay when I retire?

**Future Me answers those questions.** It turns each customer's everyday banking
into a personal timeline of their financial future:

- *"At this pace, you can buy a €320k home in spring 2031."*
- *"Your car is 9 years old. Expect a replacement around 2027."*
- *"Retirement: you're on track for 68% of your current income."*

The timeline moves with her. She gets a raise, and the house moves to 2030. She
adds €100 a month, and it moves again. She sees the result of every choice
before she makes it. She can also play "what if": a baby, a sabbatical, a move
to Ghent.

KBC stops reacting to what customers did and starts helping with what's coming.
The advisor conversation starts from the timeline, not from zero. Offers show up
when they move a date forward, not when a campaign runs.

It scales because the forecasts are simple, cheap calculations on data KBC
already has. AI only steps in to explain a shift or spot a life event coming up.
One engine, 2.3 million personal futures.

**KBC doesn't just show you your money. It shows you your future, and helps you
get there sooner.**

---

## Run it

```bash
docker compose up --build
```

| | |
|---|---|
| App | <http://localhost:3000> |
| API | <http://localhost:8000/api/health> |
| API docs | <http://localhost:8000/docs> |

No API key needed, and all data is synthetic. First boot takes about 15 seconds:
it generates 1,000 customers with 12 months of transactions and runs a
benchmark in the background.

Without Docker: `./run.sh` serves the same two URLs.

To have Claude write the explanations instead of the built-in templates, set
`ANTHROPIC_API_KEY` before starting. Everything else works the same without it.

---

## The demo

The screen shows a KBC Mobile-style phone next to a small presenter panel. Pick a
customer at the top. In the panel, each button sends one real-life transaction,
and the phone's timeline updates. Dates that moved get a badge, for example
"5 months sooner".

The phone has three tabs:

- **Start**: what KBC Mobile shows today. Accounts, recent transactions, and a
  "For you" card that links to Future Me.
- **Future Me**: a headline ("At this pace, your home deposit of €50,000 is
  ready in July 2032"), a **What if…** panel and the timeline. The panel has a
  slider to save more each month and a 6-month sabbatical toggle. Both only
  preview the change and save nothing.
- **About me**: what the plan is built on.
  - **Your goals**: filled in automatically for the customer's stage of life.
    For example, a home deposit for renters aged 20 to 45, or a driving licence
    for teenagers (lessons from 17, exam at 18). Each goal can be changed or removed with ×, and put back
    later.
  - **Add a goal**: one-tap presets (travel around the world, a car, a wedding,
    a sabbatical) or a goal of your own with a name and an amount.
  - **About you**: stage of life (with the reasons for our guess), household
    and retirement age. Below that, the guesses we're unsure about.

**Noah, 15, Hasselt: driving licence.** In Belgium you can learn to drive from
17 and take the practical exam at 18. His plan starts with a driving licence
(€1,500) that he needs by 17, when lessons start. The timeline also shows the
exam at 18. Saving €40 of pocket money a month, he has the money in time. The
**What if** slider and **Saves birthday money** bring that date closer.

**Lotte, 23, Leuven: first job.** She has had exactly one salary payment, so we
don't count it as a pattern yet. Click **Second salary arrives** and "First
recurring salary" appears on her timeline.

**An, 31, Ghent: maybe a baby.** Some baby-shop and prenatal spending puts the
"family expansion" guess at 45%, below the threshold, so the app stays quiet.
Click **Buys a crib** and it rises to 78%. Kate asks "Are you expecting a baby?",
says it's only a guess, and a family buffer enters her plan. Her home deposit
moves 5 months later. **No, remove it** takes it all back out.

**Marc, 58, Mechelen: nearing retirement.** His headline is his expected pension
income as a share of his salary. **Pays for a new kitchen** lowers it a little
and adds a renovation goal. **Moves money to savings** moves things the other
way.

The **Advisor** view reads the same data as the customer app, from the same API.

---

## How it works

In the code, a customer's model of their future is called the **Twin**.

```
transactions  ->  features  ->  life-event scoring  ->  Twin  ->  API  ->  app / advisor
                  (Tier 1)      (Tier 2)                                    |
                                                                  explanation text (Tier 3)
```

- **Tier 1, features** (`features.py`): each transaction updates about 56
  running numbers per customer (income, savings rate, rent, recurring costs,
  emergency-fund months, and so on). Seeding, the live event queue and the
  benchmark all use the same function.
- **Tier 2, scoring** (`scoring.py`): rule-based models that score life events
  and life phases. Every rule that fires adds a piece of evidence, so each
  conclusion comes with its reasons. Inferences are capped at 97% confidence;
  only the customer can make something certain.
- **Twin and projections** (`twin_engine.py`): goals, timeline, retirement
  projection and customer corrections. Plain arithmetic, no AI.
- **Tier 3, wording** (`llm.py`): Claude turns the finished result into a couple
  of sentences. It never calculates anything. Without an API key, a template
  does the same job.

Every value is labelled as **observed** (it happened), **derived** (arithmetic),
**inferred** (a guess that may be wrong) or **declared** (the customer said so),
and the UI shows that label.

In production, the in-process queue would become Kafka partitioned by customer,
the worker a stream processor, and SQLite a feature store. Each customer is
processed by one writer in order, so it scales out without locks.

---

## Scale and cost

Measured by `app/benchmark.py` on a laptop (Docker, 8 cores, Python 3.12):
100,000 customers and 1.2 million events in 6.8 seconds, about **176,000 events
per second** on one core. The app shows the numbers from the run on your own
machine. The benchmark covers the feature and scoring engine only, not storage
or network.

Extrapolated, 2.3 million customers take about 2.6 minutes on one worker.

AI is only called when a customer's future meaningfully changes or they open the
app: about 3.7 million calls a month instead of 103.5 million if we called it on
every transaction, roughly 28 times fewer. The cost assumptions are in
`.env.example` and are estimates, not quoted prices.

Run it yourself:

```bash
python scripts/benchmark.py --customers 250000 --events 12
```

---

## Tests

```bash
cd backend && python -m pytest    # 30 tests
./scripts/smoke_test.sh           # end-to-end checks against a running stack
```

---

## Repository

```
backend/app/
  main.py           API
  features.py       Tier 1: feature updates
  scoring.py        Tier 2: scoring models and thresholds
  twin_engine.py    goals, timeline, projections, corrections
  llm.py            Tier 3: Claude or template
  playbooks.py      suggested actions per life moment
  personas.py       the four demo customers
  seed.py           1,000 synthetic customers
  event_bus.py      in-process event queue
  benchmark.py      throughput and cost model
frontend/           plain ES modules served by nginx, no build step
  src/views/        customer.js, advisor.js, architecture.js
scripts/            standalone benchmark and smoke test
```

The styling uses KBC's public design tokens. No KBC logo or proprietary assets
are included.

---

## Limitations

- The scoring models are hand-written rules, tuned on synthetic data. Real
  models would need real outcome data.
- The retirement projection is simplified (75% income replacement, capped state
  pension estimate, no investment return). The assumptions are shown in the UI.
  It is not financial advice.
- The prototype covers the timeline, goals (including a house deposit), the
  retirement projection and a few what-if events. Other ideas from the pitch,
  like car replacement, a sabbatical or moving city, are not built yet.
- No authentication. SQLite is fine for one demo box, not for production.
- Customer corrections never expire.
- The Claude path is implemented but the demo was tested without an API key.
- Synthetic data only. A real version would need to go through KBC's legal,
  risk, security and GDPR review.
