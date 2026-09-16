"""Unit tests for src/common.py on small hand-made strings."""
import math

import pandas as pd
import pytest

from src import common as C

BRANDS_CFG = {
    "our_brand": ["Ozempic"],
    "our_inn": ["semaglutide"],
    "competitors": {
        "Mounjaro": ["Mounjaro"], "Wegovy": ["Wegovy"], "Zepbound": ["Zepbound"], "Rybelsus": ["Rybelsus"],
        "Trulicity": ["Trulicity"], "Victoza": ["Victoza"], "Jardiance": ["Jardiance"], "Saxenda": ["Saxenda"],
    },
    "competitor_inn": {"tirzepatide": ["Mounjaro", "Zepbound"]},
}
MIN_CHARS = 100
FILLER = "Ozempic is a once-weekly injection; talk to your clinician about dose changes and side effects. " * 2  # > 100 chars, ends with '.'


@pytest.fixture
def bd():
    return C.BrandDictionary(BRANDS_CFG)


# --------------------------------------------------------------------------- tail cleaning
def test_chip_accessdata_plus_one_is_stripped_not_truncation():
    raw = FILLER + " accessdata.fda +1"
    clean, tail_cleaned, chip = C.clean_tail(raw)
    assert clean == FILLER.rstrip()
    assert tail_cleaned and chip
    assert C.exclusion_reason(clean, raw, MIN_CHARS) is None


def test_chip_stack_and_bracket_forms():
    raw = FILLER + " [pmc.ncbi.nlm.nih] +2 [accessdata.fda] FDA Access Data"
    clean, tail_cleaned, chip = C.clean_tail(raw)
    assert clean == FILLER.rstrip()
    assert C.exclusion_reason(clean, raw, MIN_CHARS) is None


def test_trailing_emoji_is_stripped_and_not_truncation():
    raw = FILLER.rstrip() + " You've got this! 💪"
    clean, tail_cleaned, chip = C.clean_tail(raw)
    assert clean.endswith("You've got this!")
    assert tail_cleaned and not chip
    assert C.exclusion_reason(clean, raw, MIN_CHARS) is None


def test_emoji_with_variation_selector_and_zwj():
    raw = FILLER.rstrip() + " ❤️ 👩‍⚕️"
    clean, _, _ = C.clean_tail(raw)
    assert clean == FILLER.rstrip()


def test_cut_mid_word_before_fda_access_data_is_chip_on_cut():
    raw = FILLER.rstrip() + " Ozempic (semaglutide) is contraind FDA Access Data"
    clean, _, chip = C.clean_tail(raw)
    assert chip and clean.endswith("is contraind")
    assert C.chip_on_cut(raw)
    assert C.exclusion_reason(clean, raw, MIN_CHARS) == "chip_on_cut"


def test_cut_mid_sentence_without_chip_is_truncated():
    raw = FILLER.rstrip() + " there's a very good chance her care team can find a"
    clean, tail_cleaned, _ = C.clean_tail(raw)
    assert not tail_cleaned
    assert C.exclusion_reason(clean, raw, MIN_CHARS) == "truncated"


def test_too_short_after_cleaning_takes_precedence():
    raw = "No. Ozempic (semaglutide) is contraind FDA Access Data +1 FDA Access Data"
    clean, _, _ = C.clean_tail(raw)
    assert len(clean) < MIN_CHARS
    assert C.exclusion_reason(clean, raw, MIN_CHARS) == "too_short"


def test_plain_terminal_endings_pass():
    for end in [".", "!", "?", ")", "»", '"']:
        raw = FILLER.rstrip()[:-1] + end
        assert C.exclusion_reason(raw, raw, MIN_CHARS) is None, end


def test_plain_trailing_whitespace_is_not_a_cleaned_tail():
    raw = FILLER + "   \n"
    clean, tail_cleaned, chip = C.clean_tail(raw)
    assert clean == FILLER.rstrip() and not tail_cleaned and not chip


# --------------------------------------------------------------------------- brand matching
def test_inn_only_answer(bd):
    text = "Semaglutide is a GLP-1 receptor agonist used for type 2 diabetes."
    assert not bd.we_present(text)
    assert bd.inn_present(text)
    assert bd.competitors_present(text) == []
    assert bd.our_position(text) is None
    assert bd.classify_prompt(text) == "C1"  # INN never counts as a brand


def test_word_boundaries_and_case(bd):
    assert bd.we_present("Is OZEMPIC safe?")
    assert bd.we_present("Ozempic's label says…")
    assert bd.we_present("(Ozempic) or [Ozempic]")
    assert not bd.we_present("ozempicx is not a brand")
    assert not bd.we_present("nonozempic")
    assert bd.competitors_present("Mounjaro, then Wegovy.") == ["Mounjaro", "Wegovy"]


def test_classify_prompt(bd):
    assert bd.classify_prompt("What daily habits improve blood sugar?") == "C1"
    assert bd.classify_prompt("Is Ozempic safe in pregnancy?") == "C2"
    assert bd.classify_prompt("Does Mounjaro cause nausea?") == "C3"
    assert bd.classify_prompt("Ozempic vs Mounjaro for weight loss") == "C4"
    assert bd.classify_prompt("semaglutide vs tirzepatide") == "C1"


def test_expected_classes_for_status():
    assert C.expected_classes_for_status("own") == {"C2"}
    assert C.expected_classes_for_status("comp") == {"C3"}
    assert C.expected_classes_for_status("mixed") == {"C1", "C4"}


# --------------------------------------------------------------------------- position extraction
def test_mounjaro_before_ozempic(bd):
    text = "Mounjaro (tirzepatide) often produces more weight loss than Ozempic; Wegovy is a third option, and Mounjaro again."
    pos = bd.positions(text)
    assert pos == {"Mounjaro": 1, "Ozempic": 2, "Wegovy": 3}
    assert bd.our_position(text) == 2
    assert bd.competitor_positions(text) == {"Mounjaro": 1, "Wegovy": 3}
    assert bd.brands_present(text) == ["Mounjaro", "Ozempic", "Wegovy"]


def test_ozempic_first(bd):
    text = "Ozempic and Mounjaro are both GLP-1 drugs."
    assert bd.our_position(text) == 1
    assert bd.competitor_positions(text) == {"Mounjaro": 2}


def test_position_uses_first_appearance_not_count(bd):
    text = "Wegovy. Ozempic. Wegovy. Wegovy."
    assert bd.positions(text) == {"Wegovy": 1, "Ozempic": 2}


# --------------------------------------------------------------------------- domains
def test_url_host_and_registrable_domain():
    assert C.url_host("https://www.Mayoclinic.org/x?y=1") == "mayoclinic.org"
    assert C.url_host("ema.europa.eu") == "ema.europa.eu"  # bare domain without scheme
    assert C.url_host("") == "" and C.url_host(None) == ""
    assert C.registrable_domain("pmc.ncbi.nlm.nih.gov") == "nih.gov"
    assert C.registrable_domain("sub.mayoclinic.org") == "mayoclinic.org"
    assert C.registrable_domain("boltpharmacy.co.uk") == "boltpharmacy.co.uk"
    assert C.registrable_domain("x.nhs.uk") == "nhs.uk"
    assert C.registrable_domain("nhs.uk") == "nhs.uk"


def test_match_domain_list_longest_suffix():
    entries = ["lilly.com", "mounjaro.lilly.com", "zepbound.lilly.com"]
    assert C.match_domain_list("mounjaro.lilly.com", entries) == "mounjaro.lilly.com"
    assert C.match_domain_list("enrollment.mounjaro.lilly.com", entries) == "mounjaro.lilly.com"
    assert C.match_domain_list("pi.lilly.com", entries) == "lilly.com"
    assert C.match_domain_list("notlilly.com", entries) is None
    assert C.match_domain_list("lilly.com.evil.net", entries) is None


# --------------------------------------------------------------------------- Wilson CI / aggregation
def test_wilson_ci_known_values():
    lo, hi = C.wilson_ci(50, 100)
    assert abs(lo - 0.4038) < 1e-3 and abs(hi - 0.5962) < 1e-3
    assert C.wilson_ci(0, 10)[0] == 0.0
    assert C.wilson_ci(10, 10)[1] == 1.0
    assert all(math.isnan(v) for v in C.wilson_ci(0, 0))


def test_share_with_ci():
    r = C.share_with_ci([1, 0, 1, 1])
    assert r["n"] == 4 and r["share"] == 0.75 and r["ci_lo"] < 0.75 < r["ci_hi"]


def test_aggregate_bottom_up_equal_family_weights():
    # family A: one model, 2 prompts (1.0 and 0.0 after repeat-mean) -> 0.5
    # family B: two versions pooled, 3 prompt×model groups all 1.0 -> 1.0 ; overall = mean(0.5, 1.0) = 0.75
    rows = [
        ("P1", "R1", "a1", "A", 1), ("P1", "R1", "a1", "A", 1),
        ("P2", "R1", "a1", "A", 0),
        ("P1", "R1", "b1", "B", 1), ("P2", "R1", "b1", "B", 1), ("P1", "R1", "b2", "B", 1),
    ]
    df = pd.DataFrame(rows, columns=["pid", "run", "model", "model_family", "v"])
    out = C.aggregate_bottom_up(df, "v")
    assert len(out["pm"]) == 5
    fam = out["family"].set_index("model_family")["v"].to_dict()
    assert fam == {"A": 0.5, "B": 1.0}
    assert abs(float(out["overall"]["v"].iloc[0]) - 0.75) < 1e-12
    assert int(out["overall"]["n_groups"].iloc[0]) == 5
    weighted = C.aggregate_bottom_up(df, "v", family_weights={"A": 3, "B": 1})
    assert abs(float(weighted["overall"]["v"].iloc[0]) - 0.625) < 1e-12


def test_topic_group_rule():
    assert C.topic_group("Efficacy", "GI & nausea", "Z") == ("Efficacy × GI & nausea", "topic×subtopic")
    assert C.topic_group("Efficacy", None, "Z") == ("Efficacy × Z", "topic×zone")
    assert C.topic_group("Efficacy", "Other", "Z") == ("Efficacy × Z", "topic×zone")


def test_to_float_or_none():
    assert C.to_float_or_none("") is None and C.to_float_or_none(None) is None
    assert C.to_float_or_none("85") == 85.0 and C.to_float_or_none(3) == 3.0
    assert C.to_float_or_none("abc") is None
