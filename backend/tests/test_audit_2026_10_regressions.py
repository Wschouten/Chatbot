"""Regression tests for the fixes from AUDIT-2026-10-09.md (Fase 1).

Each test is named after the finding it guards. The finding ids (C1…C6) refer to
section 1 of the audit report.
"""
import os
import uuid
from unittest.mock import MagicMock, patch

from tests.conftest import INTEGRATION_KEYS


def _make_client():
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.limiter.enabled = False
    flask_app.rag_engine.get_answer = MagicMock(return_value="RAG answer")
    return flask_app, flask_app.app.test_client()


def _sid() -> str:
    return f"test_audit_{uuid.uuid4().hex[:8]}"


def _post(client, message, sid):
    resp = client.post("/api/chat", json={"message": message, "session_id": sid})
    assert resp.status_code == 200, resp.data
    return resp.get_json()


# ---------------------------------------------------------------------------
# C2: the suite must never reach live services, even with a filled-in .env
# ---------------------------------------------------------------------------

def test_integration_keys_are_blank_during_tests():
    import app as flask_app  # noqa: F401 — load_dotenv has run by now

    leaked = [k for k in INTEGRATION_KEYS if os.environ.get(k)]
    assert not leaked, f"Live credentials visible to the test suite: {leaked}"


# ---------------------------------------------------------------------------
# C1: the escalation email must carry the customer's question and name
# ---------------------------------------------------------------------------

def test_escalation_email_contains_question_and_name():
    from email_client import EmailClient

    env = {"MAILERSEND_API_KEY": "k", "SMTP_FROM_EMAIL": "bot@x.nl", "SMTP_TO_EMAIL": "ks@x.nl"}
    with patch.dict(os.environ, env), patch("email_client.http_requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        EmailClient().send_email("Jan", "jan@example.nl", "Ik wil bestelling BS12345 annuleren", [])

    body = post.call_args.kwargs["json"]["text"]
    assert "Ik wil bestelling BS12345 annuleren" in body
    assert "Jan" in body


def test_forwarded_phone_number_reaches_the_email():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {
        "state": "inactive", "handoff_done": True, "language": "nl",
        "name": "Jan", "email": "jan@example.nl",
    })
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email", return_value={"ticket": {}}) as send:
        _post(client, "Bel me even op 0612345678", sid)

    assert send.called
    question = send.call_args.args[2]
    assert "0612345678" in question


# ---------------------------------------------------------------------------
# C4: a failed send must never be reported to the customer as forwarded
# ---------------------------------------------------------------------------

def test_failed_escalation_is_not_reported_as_sent():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {
        "state": "awaiting_email", "language": "nl", "name": "Jan",
        "question": "Ik wil een collega spreken", "chat_history": [],
    })
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email", return_value=None):
        data = _post(client, "jan@example.nl", sid)

    assert "doorgestuurd" not in data["response"]
    assert "ging iets mis" in data["response"]
    # Not marked as handed off, so asking again retries instead of "al bij een collega".
    assert not flask_app.get_session_state(sid).get("handoff_done")


# ---------------------------------------------------------------------------
# C5: a missing session id must never map visitors onto one shared session
# ---------------------------------------------------------------------------

def test_null_session_id_is_never_shared():
    flask_app, client = _make_client()
    seen = []
    real_get = flask_app.get_session_state

    def spy(session_id):
        seen.append(session_id)
        return real_get(session_id)

    with patch.object(flask_app, "get_session_state", side_effect=spy):
        for _ in range(2):
            resp = client.post("/api/chat", json={"message": "Hallo", "session_id": None})
            assert resp.status_code == 200

    for sid in seen:  # minted ids are not test_-prefixed, so conftest won't purge them
        for path in (f"data/sessions/{sid}.json", f"data/logs/chat_{sid}.json"):
            if os.path.exists(path):
                os.remove(path)

    assert len(seen) == 2
    assert seen[0] != seen[1], "two visitors without a session id shared one session"
    assert "unknown_session" not in seen


# ---------------------------------------------------------------------------
# C6: every path into the handoff goes through _start_handoff
# ---------------------------------------------------------------------------

def _tracking_state(**extra):
    import datetime
    state = {
        "awaiting_order_number": True,
        "tracking_timestamp": datetime.datetime.now().isoformat(),
        "language": "nl",
        "chat_history": [{"role": "user", "content": "Waar is mijn pakket?"},
                         {"role": "assistant", "content": "Wat is je zendingnummer?"}],
    }
    state.update(extra)
    return state


def _shipping(status):
    client = MagicMock()
    client.get_shipment_status.return_value = (
        {"success": True, "status": "delivered", "description": "Afgeleverd"}
        if status == "found" else {"success": False, "status": status}
    )
    return client


def test_frustration_after_completed_handoff_does_not_restart_it():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {
        "state": "inactive", "handoff_done": True, "language": "nl",
        "name": "Jan", "email": "jan@example.nl",
        "chat_history": [{"role": "user", "content": "Hoe lang duurt het?"},
                         {"role": "assistant", "content": "Een paar dagen."}],
    })
    data = _post(client, "Ik ben erg teleurgesteld", sid)

    assert "naam" not in data["response"].lower()
    assert flask_app.get_session_state(sid).get("state") != "awaiting_name"


def test_flow_dead_end_skips_the_name_when_known():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _tracking_state(name="Jan"))
    _post(client, "eh momentje", sid)
    data = _post(client, "even zoeken", sid)

    assert "e-mailadres" in data["response"]
    assert flask_app.get_session_state(sid).get("state") == "awaiting_email"


def test_flow_attempts_reset_after_a_successful_lookup():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _tracking_state())
    with patch.object(flask_app, "get_shipping_client", return_value=_shipping("found")):
        _post(client, "eh momentje", sid)        # miss 1
        _post(client, "400000001", sid)          # found — flow ends
    state = flask_app.get_session_state(sid)
    assert "flow_attempts" not in state

    flask_app.save_session_state(sid, _tracking_state(**{k: v for k, v in state.items()
                                                           if k != "awaiting_order_number"}))
    data = _post(client, "even zoeken", sid)     # first miss of a new flow
    assert flask_app.get_session_state(sid).get("state") != "awaiting_name", data["response"]


def test_two_unknown_shipment_numbers_still_escalate():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _tracking_state())
    with patch.object(flask_app, "get_shipping_client", return_value=_shipping("not_found")):
        _post(client, "400000001", sid)
        data = _post(client, "400000002", sid)

    assert "naam" in data["response"].lower()
    assert flask_app.get_session_state(sid).get("state") == "awaiting_name"


# ---------------------------------------------------------------------------
# 1.8: the Shopify order-number → postcode flow is gone
# ---------------------------------------------------------------------------

def test_order_number_in_a_pickup_question_does_not_ask_for_a_postcode():
    flask_app, client = _make_client()
    data = _post(client, "Kan ik bestelling 12345 zelf afhalen?", _sid())
    assert "postcode" not in data["response"].lower()


def test_order_word_in_a_purchase_question_does_not_ask_for_a_postcode():
    flask_app, client = _make_client()
    data = _post(client, "Ik plaats een bestelling 5 m3 Frans boomschors, wat kost dat?", _sid())
    assert "postcode" not in data["response"].lower()


def test_tracking_question_with_shipment_number_is_looked_up_right_away():
    flask_app, client = _make_client()
    shipping = _shipping("found")
    with patch.object(flask_app, "get_shipping_client", return_value=shipping):
        data = _post(client, "Waar is mijn zending 4208360360?", _sid())

    shipping.get_shipment_status.assert_called_once_with("4208360360")
    assert "zendingnummer** door" not in data["response"]


# ---------------------------------------------------------------------------
# 1.6: a phone mention during the handoff never wipes it
# ---------------------------------------------------------------------------

def _handoff_state(state, **extra):
    s = {"state": state, "language": "nl", "question": "Mijn zakken kwamen kapot aan",
         "chat_history": []}
    s.update(extra)
    return s


def test_customer_number_during_handoff_is_forwarded():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _handoff_state("awaiting_email", name="Jan"))
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email",
                      return_value={"ticket": {}}) as send:
        data = _post(client, "Ik heb geen mail, je kunt mij telefonisch bereiken op 0612345678", sid)

    assert send.called, "the handoff was dropped instead of escalated"
    name, _email, question = send.call_args.args[:3]
    assert name == "Jan"
    assert "0612345678" in question and "kapot" in question
    assert "telefonisch" in data["response"]
    assert "0516" not in data["response"], "answered with our number instead"


def test_customer_number_before_the_name_is_kept():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _handoff_state("awaiting_name"))
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email",
                      return_value={"ticket": {}}) as send, \
         patch.object(flask_app.rag_engine, "detect_ticket_intent", return_value="giving_name"), \
         patch.object(flask_app.rag_engine, "extract_name", return_value="Jan"):
        first = _post(client, "bel me maar op 0612345678", sid)
        assert "naam" in first["response"].lower()
        _post(client, "Jan", sid)  # no email asked: the number is enough

    assert send.called
    assert "0612345678" in send.call_args.args[2]


def test_asking_our_number_during_handoff_pauses_it():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _handoff_state("awaiting_email", name="Jan"))
    data = _post(client, "Wat is jullie telefoonnummer?", sid)

    assert "0516" in data["response"]
    assert flask_app.get_session_state(sid).get("name") == "Jan", "the handoff was wiped"


def test_offering_your_own_number_is_not_a_question_about_ours():
    from app import PHONE_CONTACT_RE

    assert not PHONE_CONTACT_RE.search("Mag ik je mijn telefoonnummer geven?")
    assert PHONE_CONTACT_RE.search("Wat is je telefoonnummer?")


# ---------------------------------------------------------------------------
# 1.7: the dead-end loop detector looks at the last two answers only
# ---------------------------------------------------------------------------

_DEAD_END = "Neem contact op via klantenservice@boomschors.nl."


def _turns(*answers):
    history = []
    for a in answers:
        history += [{"role": "user", "content": "vraag"}, {"role": "assistant", "content": a}]
    return history


def test_loop_detector_ignores_non_consecutive_contact_mentions():
    from app import _detect_dead_end_loop

    assert not _detect_dead_end_loop(_turns(_DEAD_END, "Minimaal 8 cm.", _DEAD_END))
    assert _detect_dead_end_loop(_turns("Minimaal 8 cm.", _DEAD_END, _DEAD_END))


def test_declining_the_handoff_stops_the_loop_escalation():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {
        "state": "awaiting_name", "language": "nl", "question": "x",
        "chat_history": _turns(_DEAD_END, _DEAD_END),
    })
    with patch.object(flask_app.rag_engine, "detect_ticket_intent", return_value="declining"):
        _post(client, "nee hoeft niet", sid)
    data = _post(client, "Hoe dik moet ik strooien?", sid)

    assert data["response"] == "RAG answer", data["response"]


# ---------------------------------------------------------------------------
# Fase 2 — router: pre-purchase questions, quantities and dates, flow escapes
# ---------------------------------------------------------------------------

def test_delivery_area_question_is_not_tracking():
    from app import classify_intent

    assert classify_intent("Wanneer kunnen jullie leveren in Friesland?") != "tracking"
    assert classify_intent("Heb donderdag palen besteld, wanneer kan ik deze verwachten?") == "tracking"


def test_needing_only_a_little_is_not_a_manco():
    from app import classify_intent

    assert classify_intent("Ik heb maar 3 kuub nodig, wat kost dat?") != "escalate_topic"
    assert classify_intent("Ik had 3 bigbags besteld maar er is maar 1 geleverd") == "escalate_topic"


def test_quantities_and_dates_are_not_order_numbers():
    from app import extract_order_identifier

    assert extract_order_identifier("Wat kost 1000 liter boomschors?") == (None, False)
    assert extract_order_identifier("ik heb op 12-05-2026 besteld") == (None, False)
    assert extract_order_identifier("ik heb wel 2000 liter nodig") == (None, False)
    assert extract_order_identifier("het gaat om BS 6049") == ("BS6049", False)
    assert extract_order_identifier("400000001") == ("400000001", True)


def test_order_change_inside_tracking_flow_reaches_a_colleague():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _tracking_state())
    data = _post(client, "ik wil mijn bestelling annuleren", sid)

    assert "zendingnummer" not in data["response"].lower()
    assert flask_app.get_session_state(sid).get("state") == "awaiting_name"


def test_broken_phone_inside_tracking_flow_is_escalated_not_answered_with_our_number():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _tracking_state())
    _post(client, "jullie telefoon werkt niet", sid)

    assert flask_app.get_session_state(sid).get("state") == "awaiting_name"


def test_other_question_inside_tracking_flow_is_answered():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _tracking_state())
    data = _post(client, "Hoe dik moet ik boomschors strooien?", sid)

    assert data["response"] == "RAG answer"
    assert not flask_app.get_session_state(sid).get("awaiting_order_number")


# ---------------------------------------------------------------------------
# Fase 2 — every canned reply is recorded in chat_history
# ---------------------------------------------------------------------------

def test_every_canned_reply_is_recorded_in_history():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {"state": "inactive", "language": "nl", "chat_history": []})
    walk = [
        "Waar is mijn pakket?",           # tracking prompt
        "eh momentje",                    # flow re-prompt
        "Wat is jullie telefoonnummer?",  # phone shortcut (leaves the flow)
        "bedankt",                        # closing shortcut
        "Ik wil een collega spreken",     # handoff opening
    ]
    for i, message in enumerate(walk, start=1):
        _post(client, message, sid)
        history = flask_app.get_session_state(sid).get("chat_history", [])
        assert history[-2:][0]["content"] == message, f"turn not recorded: {message!r}"
        assert len(history) == min(2 * i, 10)


# ---------------------------------------------------------------------------
# Fase 2 — "oké" after a question, unit-less counts, StatusWeb negations
# ---------------------------------------------------------------------------

def _after_bot(question):
    return {"state": "inactive", "language": "nl", "chat_history": [
        {"role": "user", "content": "Mijn bigbag is gescheurd"},
        {"role": "assistant", "content": question},
    ]}


def test_ok_to_a_colleague_offer_starts_the_handoff():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _after_bot("Wil je dat ik een collega laat meekijken?"))
    data = _post(client, "Oké", sid)

    assert "graag gedaan" not in data["response"].lower()
    state = flask_app.get_session_state(sid)
    assert state.get("state") == "awaiting_name"
    assert state.get("question") == "Mijn bigbag is gescheurd"


def test_ok_to_another_question_goes_to_the_rag():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _after_bot("Zal ik uitrekenen hoeveel je nodig hebt?"))
    data = _post(client, "ok", sid)
    assert data["response"] == "RAG answer"


def test_thanks_still_closes():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _after_bot("Kan ik je nog ergens mee helpen?"))
    data = _post(client, "bedankt", sid)
    assert "graag gedaan" in data["response"].lower()


def test_unit_less_count_is_not_a_dimension():
    from volume_calc import compute_volume

    assert compute_volume("hoeveel bigbags voor 2 borders van 10 m bij 1 m?") is None
    assert "2 m3" in compute_volume("4 bij 5 meter en 10 cm dik, hoeveel kuub")


def test_statusweb_negation_is_not_reported_as_delivered():
    from app import format_shipping_response
    from shipping_api import classify_status

    for desc in ("Niet afgeleverd - klant niet thuis", "Wordt bezorgd", "Iets onbekends"):
        reply = format_shipping_response(
            {"success": True, "status": classify_status(desc),
             "details": {"status_description": desc}}, "400000001")
        assert "🎉" not in reply, (desc, reply)
        assert desc in reply
    assert classify_status("Afgeleverd") == "delivered"


# ---------------------------------------------------------------------------
# Fase 2 — output gate on the unknown path, email inside a sentence
# ---------------------------------------------------------------------------

def test_unknown_path_output_goes_through_the_gate():
    from rag_engine import RagEngine, _safe_fallback

    engine = RagEngine.__new__(RagEngine)
    engine.chat_model = "x"
    engine.openai_client = MagicMock()
    engine.openai_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="这是一个测试回答"))]  # foreign script

    assert engine.generate_helpful_unknown_response("vraag", "nl") == _safe_fallback("nl")


def test_email_inside_a_sentence_is_accepted():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _handoff_state("awaiting_email", name="Jan"))
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email",
                      return_value={"ticket": {}}) as send:
        _post(client, "mijn mail is jan@example.nl.", sid)

    assert send.called
    assert send.call_args.args[1] == "jan@example.nl"


def test_second_invalid_email_offers_the_phone():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, _handoff_state("awaiting_email", name="Jan"))
    with patch.object(flask_app.rag_engine, "detect_ticket_intent", return_value="giving_name"):
        first = _post(client, "jan at example", sid)
        second = _post(client, "jan op example", sid)

    assert "telefoonnummer" not in first["response"]
    assert "telefoonnummer" in second["response"]


# ---------------------------------------------------------------------------
# Fase 2 — ingestion: no duplicate tail chunk, a partial embed is retried
# ---------------------------------------------------------------------------

def _engine_with_collection(embed=lambda text: [0.0]):
    from rag_engine import RagEngine

    engine = RagEngine.__new__(RagEngine)
    engine.collection = MagicMock()
    engine._get_embedding = MagicMock(side_effect=embed)
    return engine


def test_chunker_emits_no_duplicate_tail_chunk():
    engine = _engine_with_collection()
    text = "x" * 1900  # one chunk; the last 200 chars used to come back as a second one
    assert engine._ingest_text_chunks(text, "f.txt") == 1


def test_partial_embed_failure_removes_the_file_for_a_retry():
    calls = {"n": 0}

    def flaky(text):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("429")
        return [0.0]

    engine = _engine_with_collection(flaky)
    text = ("regel\n" * 400)  # ~2400 chars → two chunks
    assert engine._ingest_text_chunks(text, "f.txt") == 0
    engine.collection.delete.assert_called_once_with(where={"source": "f.txt"})


# ---------------------------------------------------------------------------
# Fase 2 — privacy: portal.db orphans, served portal tree
# ---------------------------------------------------------------------------

def test_portal_metadata_of_deleted_logs_is_purged(tmp_path):
    import sqlite3
    import admin_db

    db = tmp_path / "portal.db"
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "chat_sess_keep.json").write_text("[]")
    with patch.dict(os.environ, {"PORTAL_DB_PATH": str(db)}):
        from app import app as flask_app
        with flask_app.app_context():
            admin_db.init_db()
            admin_db.upsert_metadata("sess_keep", status="open")
            admin_db.upsert_metadata("sess_gone", status="open")
            admin_db.add_note("sess_gone", "belde om 10 uur")
            admin_db.close_db()
        assert admin_db.purge_orphaned_metadata(str(logs)) == 1

    conn = sqlite3.connect(db)
    left = {r[0] for r in conn.execute("SELECT session_id FROM conversation_metadata")}
    notes = conn.execute("SELECT COUNT(*) FROM conversation_notes").fetchone()[0]
    conn.close()
    assert left == {"sess_keep"} and notes == 0


def test_empty_log_dir_never_wipes_the_portal(tmp_path):
    import admin_db

    (tmp_path / "logs").mkdir()
    (tmp_path / "portal.db").write_bytes(b"")
    with patch.dict(os.environ, {"PORTAL_DB_PATH": str(tmp_path / "portal.db")}):
        assert admin_db.purge_orphaned_metadata(str(tmp_path / "logs")) == 0


def test_only_portal_js_is_served():
    _, client = _make_client()
    assert client.get("/portal/js/storage.js").status_code == 200
    assert client.get("/portal/trainingdata/x.json").status_code == 404
