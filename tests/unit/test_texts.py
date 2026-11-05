from radiografia.analytics import costs
from radiografia.reporting.texts import DISCLAIMER, METRIC_TEXTS, WARNING_TEXTS

FORBIDDEN = ("deberías", "te recomendamos", "recomendamos", "compra ", "vende ", "cámbiate")


def test_every_cost_metric_and_warning_has_text():
    assert {costs.WEIGHTED_TER, costs.ANNUAL_COST} <= set(METRIC_TEXTS)
    assert {
        costs.WARNING_TER_IS_NOT_TOTAL_COST,
        costs.WARNING_HEDGING_COST_NOT_IN_TER,
        costs.WARNING_PARTIAL_COVERAGE,
    } <= set(WARNING_TEXTS)


def test_texts_describe_and_never_recommend():
    texts = [*WARNING_TEXTS.values()]
    for text in METRIC_TEXTS.values():
        texts += [text.title, text.one_liner, text.how_it_is_computed, *text.limitations]
    found = [(word, t) for t in texts for word in FORBIDDEN if word in t.lower()]
    assert found == []


def test_disclaimer_says_it_is_not_advice():
    assert "No es asesoramiento" in DISCLAIMER
