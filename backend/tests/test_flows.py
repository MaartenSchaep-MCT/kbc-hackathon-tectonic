"""The five critical flows from the brief, plus the invariants that hold the
architecture together."""
from __future__ import annotations

from conftest import HERO_A, HERO_B, HERO_C, goal_ids, playbook_ids, signal


# ==========================================================================
# TEST 1 - inject salary
# ==========================================================================
def test_1_inject_salary_updates_features_score_and_phase(client):
    before = client.get(f"/api/twins/{HERO_A}").json()
    assert before["life_phase"]["value"] == "student", (
        "Lotte must start as a student: one salary payment is not a pattern"
    )
    assert before["derived_features"]["salary_months_consecutive"] == 1
    assert before["derived_features"]["salary_detected"] is False
    score_before = signal(before, "first_job")["score"]

    response = client.post(f"/api/demo/{HERO_A}/first-salary?wait=true")
    assert response.status_code == 200
    after = response.json()["twin"]

    # Tier 1: the salary feature moved.
    assert after["derived_features"]["salary_months_consecutive"] == 2
    assert after["derived_features"]["salary_detected"] is True
    assert after["derived_features"]["monthly_income"] > before["derived_features"]["monthly_income"]

    # Tier 2: the first-job score increased.
    assert signal(after, "first_job")["score"] > score_before

    # Twin: the life phase changed, and the version advanced.
    assert after["life_phase"]["value"] == "first_job"
    assert after["version"] == before["version"] + 1
    assert "life_phase" in after["changed_fields"]

    # The timeline gained the milestone, and only once it was a real pattern.
    titles_before = {m["title"] for m in before["future_timeline"]}
    titles_after = {m["title"] for m in after["future_timeline"]}
    assert "First recurring salary" not in titles_before
    assert "First recurring salary" in titles_after


def test_1b_phase_change_is_explained_and_not_certain(client):
    after = client.post(f"/api/demo/{HERO_A}/first-salary?wait=true").json()["twin"]
    phase = after["life_phase"]
    assert phase["provenance"] == "inferred"
    assert phase["confidence"] < 1.0, "an inference must never claim certainty"
    assert len(phase["evidence"]) >= 3
    explanation = next(e for e in after["explanations"] if e["field"] == "life_phase")
    assert explanation["correctable"] is True
    assert any("salary" in r.lower() for r in explanation["reasons"])


# ==========================================================================
# TEST 2 - inject crib purchase
# ==========================================================================
def test_2_crib_raises_baby_signal_but_keeps_uncertainty(client):
    before = client.get(f"/api/twins/{HERO_B}").json()
    baby_before = signal(before, "possible_family_expansion")
    assert baby_before["triggered"] is False, (
        "baby-shop spending alone must not be enough to conclude anything"
    )

    after = client.post(f"/api/demo/{HERO_B}/crib-purchase?wait=true").json()["twin"]
    baby_after = signal(after, "possible_family_expansion")

    assert baby_after["score"] > baby_before["score"]
    assert baby_after["triggered"] is True

    # Uncertainty must remain explicit at every level.
    assert baby_after["score"] < 1.0
    assert "expecting_baby" in playbook_ids(after)
    playbook = next(p for p in after["playbooks"] if p["id"] == "expecting_baby")
    assert "%" in playbook["customer_explanation"]
    assert any(word in playbook["customer_explanation"].lower()
               for word in ("looks like", "not sure", "confident"))
    assert "definitely" not in playbook["customer_explanation"].lower()

    # The household change is carried as a possibility, never as a fact.
    change = next(c for c in after["household"]["possible_changes"]
                  if c["key"] == "family_expansion")
    assert change["provenance"] == "inferred"
    assert 0.0 < change["confidence"] < 1.0
    assert change["evidence"]

    # The advisor is warned not to treat it as news.
    advisor = client.get(f"/api/advisor/{HERO_B}").json()
    context = next(a for a in advisor["advisor_context"] if "baby" in a["playbook"].lower())
    assert "do not congratulate" in context["context"].lower()


# ==========================================================================
# TEST 3 - customer correction
# ==========================================================================
def test_3_house_correction_is_stored_and_suppresses_recommendations(client):
    before = client.get(f"/api/twins/{HERO_B}").json()
    assert "first_home" in playbook_ids(before)
    assert "house_deposit" in goal_ids(before)

    response = client.post(
        f"/api/twins/{HERO_B}/corrections",
        json={"field": "plans_to_buy_house", "value": False,
              "note": "I am not planning to buy a house"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "override" in body["notice"].lower()
    after = body["twin"]

    # Stored and persisted.
    assert any(c["field"] == "plans_to_buy_house" for c in after["corrections"])
    reloaded = client.get(f"/api/twins/{HERO_B}").json()
    assert any(c["field"] == "plans_to_buy_house" for c in reloaded["corrections"])

    # Suppressed everywhere, not just hidden in one view.
    assert "first_home" not in playbook_ids(after)
    assert "house_deposit" not in goal_ids(after)
    assert not any("deposit" in m["title"].lower() for m in after["future_timeline"])
    advisor = client.get(f"/api/advisor/{HERO_B}").json()
    assert not any("first home" in a["playbook"].lower() for a in advisor["advisor_context"])
    assert any(c["field"] == "plans_to_buy_house" for c in advisor["corrections"])


def test_3b_baby_correction_suppresses_the_inference(client):
    client.post(f"/api/demo/{HERO_B}/crib-purchase?wait=true")
    assert signal(client.get(f"/api/twins/{HERO_B}").json(),
                  "possible_family_expansion")["triggered"] is True

    after = client.post(
        f"/api/twins/{HERO_B}/corrections",
        json={"field": "family_expansion", "value": False, "note": "Gift for my sister"},
    ).json()["twin"]

    baby = signal(after, "possible_family_expansion")
    assert baby["suppressed_by_customer"] is True
    assert baby["triggered"] is False
    assert "expecting_baby" not in playbook_ids(after)
    assert not any(c["key"] == "family_expansion"
                   for c in after["household"]["possible_changes"])
    # The correction is visible, not silent - the customer can see it worked.
    assert any(e["field"] == "corrections" for e in after["explanations"])


def test_3c_declared_life_phase_outranks_inference(client):
    after = client.post(
        f"/api/twins/{HERO_A}/corrections",
        json={"field": "life_phase", "value": "establishing", "note": "Working full time"},
    ).json()["twin"]
    assert after["life_phase"]["value"] == "establishing"
    assert after["life_phase"]["provenance"] == "declared"
    assert after["life_phase"]["confidence"] == 1.0
    assert after["life_phase"]["source"] == "customer_correction"


def test_3d_retirement_age_correction_changes_the_projection(client):
    before = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]["retirement"]
    assert before["retirement_age_source"] == "assumed"

    after = client.post(
        f"/api/twins/{HERO_C}/corrections",
        json={"field": "target_retirement_age", "value": 62},
    ).json()["twin"]["derived_features"]["retirement"]

    assert after["target_retirement_age"] == 62
    assert after["retirement_age_source"] == "declared"
    assert after["years_to_retirement"] < before["years_to_retirement"]
    # Fewer years of contributions means less projected capital.
    assert after["projected_capital"] < before["projected_capital"]


def test_3e_rejects_fields_that_are_not_correctable(client):
    r = client.post(f"/api/twins/{HERO_A}/corrections",
                    json={"field": "progress_score", "value": 1.0})
    assert r.status_code == 400
    r = client.post(f"/api/twins/{HERO_A}/corrections",
                    json={"field": "life_phase", "value": "astronaut"})
    assert r.status_code == 400


# ==========================================================================
# TEST 4 - one Twin, every channel
# ==========================================================================
def test_4_customer_and_advisor_return_the_same_twin(client):
    for customer_id in (HERO_A, HERO_B, HERO_C):
        customer_twin = client.get(f"/api/twins/{customer_id}").json()
        advisor = client.get(f"/api/advisor/{customer_id}").json()
        assert advisor["twin_version"] == customer_twin["version"]
        assert advisor["twin"]["life_phase"] == customer_twin["life_phase"]
        assert advisor["twin"]["goals"] == customer_twin["goals"]
        assert advisor["twin"]["progress_score"] == customer_twin["progress_score"]


def test_4b_same_twin_after_an_event_from_a_different_channel(client):
    before = client.get(f"/api/twins/{HERO_C}").json()["version"]
    # An event arriving from KBC Mobile, not from core banking.
    client.post("/api/events/transaction", json={
        "customer_id": HERO_C, "merchant": "KBC Spaarrekening",
        "category": "savings_transfer", "amount": -500.0,
        "description": "Extra sparen", "channel": "kbc_mobile",
    })
    import time
    for _ in range(80):
        twin = client.get(f"/api/twins/{HERO_C}").json()
        if twin["version"] > before:
            break
        time.sleep(0.05)
    advisor = client.get(f"/api/advisor/{HERO_C}").json()
    assert twin["version"] > before, "the event must reach the Twin"
    assert advisor["twin_version"] == twin["version"], (
        "the advisor must see the update with no separate logic"
    )


def test_4c_advisor_view_contains_no_sales_targets(client):
    advisor = client.get(f"/api/advisor/{HERO_C}").json()
    blob = " ".join(
        [a["context"] for a in advisor["advisor_context"]]
        + [t["topic"] for t in advisor["conversation_topics"]]
    ).lower()
    for phrase in ("sell ", "cross-sell", "upsell", "sales target", "quota", "pitch"):
        assert phrase not in blob, f"advisor view must not contain '{phrase}'"
    assert "progress" in advisor["guardrail"].lower()


# ==========================================================================
# TEST 5 - no Anthropic key
# ==========================================================================
def test_5_works_without_an_anthropic_key(client):
    from app import config
    assert config.LLM_ENABLED is False

    status = client.get("/api/health").json()["tier3"]
    assert status["tier3_enabled"] is False
    assert status["generator"] == "template"

    twin = client.get(f"/api/twins/{HERO_A}?open=true").json()
    narrative = twin["narrative"]
    assert narrative["generator"] == "template"
    assert narrative["degraded"] is False
    assert len(narrative["body"]) > 80, "the fallback must be a real narrative"
    assert narrative["headline"]
    # The template must not pretend to be certain either.
    assert "%" in narrative["body"] or "told us" in narrative["body"]


def test_5b_template_narrative_uses_only_computed_numbers(client):
    twin = client.get(f"/api/twins/{HERO_A}?open=true").json()
    body = twin["narrative"]["body"]
    goal = twin["goals"][0]
    assert f"{goal['target_amount']:,.0f}" in body, (
        "the narrative must quote the goal target the engine computed"
    )


# ==========================================================================
# Architectural invariants
# ==========================================================================
def test_provenance_is_always_present_and_valid(client):
    valid = {"observed", "derived", "inferred", "declared"}
    twin = client.get(f"/api/twins/{HERO_B}").json()
    assert twin["life_phase"]["provenance"] in valid
    for collection in ("goals", "risks", "intent", "signals", "explanations"):
        for item in twin[collection]:
            assert item["provenance"] in valid, f"{collection} missing provenance"
    for milestone in twin["future_timeline"]:
        assert milestone["provenance"] in valid


def test_no_inference_ever_reaches_certainty(client):
    from app.scoring import MAX_INFERRED_CONFIDENCE
    for customer_id in (HERO_A, HERO_B, HERO_C):
        twin = client.get(f"/api/twins/{customer_id}").json()
        for s in twin["signals"]:
            assert s["score"] <= MAX_INFERRED_CONFIDENCE
        if twin["life_phase"]["provenance"] == "inferred":
            assert twin["life_phase"]["confidence"] <= MAX_INFERRED_CONFIDENCE


def test_one_off_expense_does_not_change_the_retirement_target(client):
    before = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]["retirement"]
    client.post(f"/api/demo/{HERO_C}/large-expense?wait=true")
    after = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]["retirement"]
    assert after["capital_needed"] == before["capital_needed"], (
        "a one-off purchase must not change what the customer needs to retire on"
    )
    assert after["projected_shortfall"] > before["projected_shortfall"], (
        "but it must reduce the capital they are projected to have"
    )


def test_extra_saving_improves_the_projection(client):
    before = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]["retirement"]
    client.post(f"/api/demo/{HERO_C}/savings-contribution?wait=true")
    after = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]["retirement"]
    assert after["projected_capital"] > before["projected_capital"]
    assert after["projected_shortfall"] < before["projected_shortfall"]


def test_savings_transfers_are_not_counted_as_spending(client):
    before = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]
    client.post(f"/api/demo/{HERO_C}/savings-contribution?wait=true")
    after = client.get(f"/api/twins/{HERO_C}").json()["derived_features"]
    assert after["monthly_spend_core"] == before["monthly_spend_core"]
    assert after["savings_balance"] > before["savings_balance"]


def test_goals_never_double_count_the_same_euro(client):
    for customer_id in (HERO_A, HERO_B, HERO_C):
        twin = client.get(f"/api/twins/{customer_id}").json()
        allocated = sum(g["current_amount"] for g in twin["goals"])
        balance = twin["derived_features"]["savings_balance"]
        assert allocated <= balance + 0.01, (
            f"{customer_id}: goals allocate {allocated} of a {balance} balance"
        )
        buffer_goals = [g for g in twin["goals"]
                        if g["id"] in ("emergency_fund", "family_buffer",
                                       "shared_buffer", "stabilise",
                                       "income_sustainability")]
        assert len(buffer_goals) <= 1, "only one buffer goal may be active"


def test_event_pipeline_is_asynchronous_and_traced(client):
    accepted = client.post("/api/events/transaction", json={
        "customer_id": HERO_A, "merchant": "Colruyt", "category": "groceries",
        "amount": -42.0, "description": "Boodschappen", "channel": "kbc_mobile",
    }).json()
    assert accepted["status"] == "queued"
    assert accepted["event_id"].startswith("EV-")

    import time
    trace = {}
    for _ in range(100):
        trace = client.get(f"/api/events/{accepted['event_id']}").json()
        if trace.get("status") == "processed":
            break
        time.sleep(0.05)
    assert trace["status"] == "processed"
    names = [s["name"] for s in trace["stages"]]
    assert "Tier 1 - feature update" in names
    assert "Tier 2 - life-event scoring" in names
    assert "Financial Twin updated" in names
    assert trace["total_ms"] > 0


def test_twin_history_is_append_only(client):
    v0 = client.get(f"/api/twins/{HERO_A}").json()["version"]
    client.post(f"/api/demo/{HERO_A}/first-salary?wait=true")
    history = client.get(f"/api/twins/{HERO_A}/history").json()["history"]
    versions = [h["version"] for h in history]
    assert v0 in versions and v0 + 1 in versions
    assert versions == sorted(versions, reverse=True)
    assert all(h["change_summary"] for h in history)


def test_benchmark_numbers_are_measured_not_hardcoded(client):
    result = client.post("/api/benchmark/run?customers=2000&events_per_customer=12").json()
    measured = result["measured"]
    assert measured["events_processed"] == 24_000
    assert measured["events_per_second"] > 0
    assert measured["wall_seconds"] > 0
    assert result["extrapolation"]["is_estimate"] is True
    assert result["extrapolation"]["equivalent_events"] > measured["events_processed"]

    # Proof the figures are measured rather than returned from a constant:
    # tripling the workload must triple the event count and take longer.
    bigger = client.post("/api/benchmark/run?customers=6000&events_per_customer=12").json()
    assert bigger["measured"]["events_processed"] == 72_000
    assert bigger["measured"]["wall_seconds"] > measured["wall_seconds"]
    # ...while the per-event rate stays in the same order of magnitude, which a
    # hardcoded number could not do either.
    ratio = bigger["measured"]["events_per_second"] / measured["events_per_second"]
    assert 0.2 < ratio < 5.0, f"throughput moved implausibly: {ratio}"


def test_cost_model_is_driven_by_configurable_assumptions(client):
    cost = client.get("/api/cost").json()
    assert cost["assumptions"]["population"] == 2_300_000
    assert cost["llm"]["monthly_calls"] < cost["naive_per_transaction"]["monthly_calls"]
    assert cost["naive_per_transaction"]["multiple_of_selective"] > 5
    assert "not a price quote" in cost["assumptions"]["price_source"].lower() or \
           "verify" in cost["assumptions"]["price_source"].lower()


def test_playbooks_are_not_sales_scripts(client):
    catalogue = client.get("/api/playbooks").json()
    assert catalogue["count"] >= 10
    blob = " ".join(
        [p["customer_explanation"] + " " + p["advisor_context"] for p in catalogue["playbooks"]]
        + [a["title"] + " " + a["why"] for p in catalogue["playbooks"] for a in p["actions"]]
    ).lower()
    for phrase in ("cross-sell", "upsell", "sales target", "close the deal", "quota"):
        assert phrase not in blob
    for p in catalogue["playbooks"]:
        for a in p["actions"]:
            assert a["customer_benefit"], f"{p['id']}/{a['id']} has no customer benefit"


def test_every_playbook_has_a_trigger_that_can_actually_fire(client):
    from app import playbooks, scoring
    signal_ids = {m.id for m in scoring.SIGNAL_MODELS}
    for p in playbooks.PLAYBOOKS:
        assert p.signal_id in signal_ids, f"{p.id} references unknown signal {p.signal_id}"


def test_health_and_architecture_endpoints(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["customers"] > 0 and health["twins"] > 0
    arch = client.get("/api/architecture").json()
    assert len(arch["tiers"]) == 3
    assert any("Kafka" in m["production"] for m in arch["production_mapping"])


def test_reset_restores_the_seeded_world(client):
    client.post(f"/api/demo/{HERO_A}/first-salary?wait=true")
    client.post(f"/api/twins/{HERO_A}/corrections",
                json={"field": "plans_to_buy_house", "value": False})
    assert client.get(f"/api/twins/{HERO_A}").json()["corrections"]
    client.post("/api/demo/reset")
    twin = client.get(f"/api/twins/{HERO_A}").json()
    assert twin["corrections"] == []
    assert twin["life_phase"]["value"] == "student"
