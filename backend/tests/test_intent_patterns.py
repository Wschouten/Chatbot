"""Regression tests for intent-detection regex patterns in app.py.

No Flask, no mocking — just import the compiled patterns and assert
match/no-match behaviour. Any change that breaks a pattern will surface here
before it reaches production.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (
    PRE_PURCHASE_RE,
    TRACKING_INTENT_RE,
    NO_ORDER_YET_RE,
    NO_SHIPMENT_NUMBER_RE,
    HUMAN_ESCALATION_RE,
    CLOSING_RE,
    FRUSTRATION_RE,
    PRIOR_CONTACT_FAILED_RE,
)


class TestPrePurchaseRE:
    """PRE_PURCHASE_RE should match hypothetical order questions only."""

    def test_matches_dutch_vandaag_bestel(self):
        assert PRE_PURCHASE_RE.search("als ik vandaag bestel wanneer")

    def test_matches_dutch_nu_bestel(self):
        assert PRE_PURCHASE_RE.search("als ik nu bestel, wanneer is het er?")

    def test_matches_english_place_order(self):
        assert PRE_PURCHASE_RE.search("if i place an order today")

    def test_matches_english_buy(self):
        assert PRE_PURCHASE_RE.search("if i buy this, when will it arrive?")

    def test_does_not_match_tracking_intent(self):
        assert not PRE_PURCHASE_RE.search("waar is mijn bestelling")

    def test_does_not_match_arrival_question(self):
        assert not PRE_PURCHASE_RE.search("wanneer komt mijn pakket")

    # --- named regression test ---
    def test_pre_purchase_does_not_match_tracking_intent(self):
        """Regression: hypothetical big-bag order must NOT match as a WISMO trigger.

        This phrase was previously misclassified, causing the bot to ask for
        an order number instead of answering the delivery-time question via RAG.
        """
        msg = "als ik vandaag een big bag bestel, wanneer wordt hij geleverd?"
        assert PRE_PURCHASE_RE.search(msg), (
            "PRE_PURCHASE_RE must match the hypothetical order phrase so "
            "WISMO is skipped and the question is routed to RAG."
        )


class TestTrackingIntentRE:
    """TRACKING_INTENT_RE should match order-status questions."""

    def test_matches_dutch_waar_is(self):
        assert TRACKING_INTENT_RE.search("waar is mijn pakket")

    def test_matches_english_where_is_my_order(self):
        assert TRACKING_INTENT_RE.search("where is my order")

    def test_matches_track(self):
        assert TRACKING_INTENT_RE.search("can you track mijn zending")

    def test_matches_dutch_mijn_bestelling(self):
        assert TRACKING_INTENT_RE.search("wanneer komt mijn bestelling aan?")

    def test_matches_shipped(self):
        assert TRACKING_INTENT_RE.search("has it been shipped yet?")

    def test_does_not_match_pre_purchase_phrase(self):
        # Raw pattern still matches "als ik vandaag bestel" because it contains
        # "vandaag" which is part of "vandaag.*lever" — test what the regex
        # actually does so we're honest about the guard being upstream.
        # The real guard is: PRE_PURCHASE_RE wins first in app logic.
        # Here we just verify the pattern is present and behaves consistently.
        msg = "als ik vandaag bestel"
        # Either match or no-match is acceptable; we record the current behaviour
        # so a future change is visible.
        result = bool(TRACKING_INTENT_RE.search(msg))
        # Document current behaviour: "vandaag" alone without "lever/bezorg" should NOT match
        assert not result, (
            "TRACKING_INTENT_RE should not match a bare pre-purchase phrase "
            "without any delivery/tracking keywords."
        )


class TestNoOrderYetRE:
    """NO_ORDER_YET_RE should detect 'I haven't ordered yet' statements."""

    def test_matches_dutch_nog_geen_bestell(self):
        assert NO_ORDER_YET_RE.search("ik heb nog geen bestelling")

    def test_matches_dutch_nog_niet_besteld(self):
        assert NO_ORDER_YET_RE.search("ik heb nog niet besteld")

    def test_matches_dutch_geen_bestelling_gedaan(self):
        assert NO_ORDER_YET_RE.search("ik heb geen bestelling gedaan")

    def test_matches_english_havent_ordered(self):
        assert NO_ORDER_YET_RE.search("I haven't ordered yet")

    def test_matches_english_no_order_yet(self):
        assert NO_ORDER_YET_RE.search("no order yet")

    def test_does_not_match_no_order_number(self):
        assert not NO_ORDER_YET_RE.search("ik heb mijn bestelnummer niet bij de hand")

    def test_does_not_match_no_shipment_number(self):
        assert not NO_ORDER_YET_RE.search("geen zendingnummer")

    # --- named regression test ---
    def test_no_order_yet_matches_common_dutch_phrase(self):
        """Regression: 'ik heb nog geen bestelnummer' must trigger the
        no-order-yet branch, not the order-lookup branch."""
        assert NO_ORDER_YET_RE.search("ik heb nog geen bestelnummer"), (
            "Phrase 'ik heb nog geen bestelnummer' must match NO_ORDER_YET_RE "
            "so the bot responds with delivery-time info, not another order-number prompt."
        )


class TestNoShipmentNumberRE:
    """NO_SHIPMENT_NUMBER_RE should detect 'I don't have the tracking number'."""

    def test_matches_dutch_geen_zendingnummer(self):
        assert NO_SHIPMENT_NUMBER_RE.search("ik heb geen zendingnummer")

    def test_matches_dutch_geen_trackingnummer(self):
        assert NO_SHIPMENT_NUMBER_RE.search("geen trackingnummer")

    def test_matches_english_dont_have_tracking(self):
        assert NO_SHIPMENT_NUMBER_RE.search("I don't have tracking")

    def test_matches_english_no_shipment(self):
        assert NO_SHIPMENT_NUMBER_RE.search("no shipment number available")

    def test_does_not_match_tracking_question(self):
        assert not NO_SHIPMENT_NUMBER_RE.search("waar is mijn pakket")

    def test_does_not_match_already_ordered(self):
        assert not NO_SHIPMENT_NUMBER_RE.search("ik heb besteld")


class TestHumanEscalationRE:
    """HUMAN_ESCALATION_RE should detect requests to speak with a human."""

    def test_matches_dutch_medewerker_spreken(self):
        assert HUMAN_ESCALATION_RE.search("ik wil een medewerker spreken")

    def test_matches_dutch_wil_een_medewerker(self):
        assert HUMAN_ESCALATION_RE.search("wil een medewerker")

    def test_matches_english_speak_to_human(self):
        assert HUMAN_ESCALATION_RE.search("I want to speak to a human")

    def test_matches_english_live_agent(self):
        assert HUMAN_ESCALATION_RE.search("connect me to a live agent")

    def test_does_not_match_tracking_question(self):
        assert not HUMAN_ESCALATION_RE.search("waar is mijn pakket")

    def test_does_not_match_closing(self):
        assert not HUMAN_ESCALATION_RE.search("dankjewel")


class TestClosingRE:
    """CLOSING_RE should match short farewell/acknowledgement messages."""

    def test_matches_dutch_dankjewel(self):
        assert CLOSING_RE.match("dankjewel")

    def test_matches_dutch_prima(self):
        assert CLOSING_RE.match("prima")

    def test_matches_dutch_ok(self):
        assert CLOSING_RE.match("ok")

    def test_matches_english_thanks(self):
        assert CLOSING_RE.match("thanks")

    def test_matches_english_thank_you(self):
        assert CLOSING_RE.match("thank you")

    def test_matches_with_trailing_punctuation(self):
        assert CLOSING_RE.match("bedankt!")

    def test_does_not_match_tracking_question(self):
        assert not CLOSING_RE.match("waar is mijn bestelling")

    def test_does_not_match_escalation(self):
        assert not CLOSING_RE.match("ik wil een medewerker")


class TestFrustrationRE:
    # --- FRUSTRATION_RE matches ---
    def test_matches_ik_baal(self):
        assert FRUSTRATION_RE.search("Ik baal behoorlijk van de email afhandeling")

    def test_matches_belachelijk(self):
        assert FRUSTRATION_RE.search("Dit is belachelijk, ik wacht al weken")

    def test_matches_onacceptabel(self):
        assert FRUSTRATION_RE.search("Dit is totaal onacceptabel")

    def test_matches_klacht(self):
        assert FRUSTRATION_RE.search("Ik wil een klacht indienen")

    def test_matches_teleurgesteld(self):
        assert FRUSTRATION_RE.search("Ik ben erg teleurgesteld in de service")

    def test_matches_english_ridiculous(self):
        assert FRUSTRATION_RE.search("This is ridiculous, I've been waiting forever")

    def test_matches_english_unacceptable(self):
        assert FRUSTRATION_RE.search("This is absolutely unacceptable")

    def test_matches_english_complaint(self):
        assert FRUSTRATION_RE.search("I want to file a complaint")

    # --- FRUSTRATION_RE non-matches ---
    def test_no_match_mild_jammer(self):
        assert not FRUSTRATION_RE.search("Dat is jammer")

    def test_no_match_niet_ideaal(self):
        assert not FRUSTRATION_RE.search("Niet ideaal, maar ik begrijp het")

    def test_no_match_pre_purchase(self):
        assert not FRUSTRATION_RE.search("Als ik vandaag bestel, wanneer komt het dan?")

    def test_no_match_tracking(self):
        assert not FRUSTRATION_RE.search("Waar is mijn pakket?")


class TestPriorContactFailedRE:
    # --- PRIOR_CONTACT_FAILED_RE matches ---
    def test_matches_vorige_mail(self):
        assert PRIOR_CONTACT_FAILED_RE.search("Mijn vorige mail is nooit beantwoord")

    def test_matches_meerdere_keren_gemaild(self):
        assert PRIOR_CONTACT_FAILED_RE.search("Ik heb al meerdere keren gemaild")

    def test_matches_geen_reactie_gekregen(self):
        assert PRIOR_CONTACT_FAILED_RE.search("Ik heb geen reactie gekregen op mijn mails")

    def test_matches_niemand_reageert(self):
        assert PRIOR_CONTACT_FAILED_RE.search("Niemand reageert op mijn berichten")

    def test_matches_english_previous_email(self):
        assert PRIOR_CONTACT_FAILED_RE.search("My previous email was ignored")

    def test_matches_english_emailed_multiple_times(self):
        assert PRIOR_CONTACT_FAILED_RE.search("I have emailed multiple times with no reply")

    # --- PRIOR_CONTACT_FAILED_RE non-matches ---
    def test_no_match_first_contact(self):
        assert not PRIOR_CONTACT_FAILED_RE.search("Ik wil graag een retour aanvragen")

    def test_no_match_tracking_question(self):
        assert not PRIOR_CONTACT_FAILED_RE.search("Wat is mijn zendingnummer?")
