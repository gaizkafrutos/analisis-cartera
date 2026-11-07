"""Recognising the same company across issuers (analytics/company_names.py)."""

import pandas as pd
import pytest

from radiografia.analytics.company_names import company_keys, normalise_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Apple Inc.", "APPLE"),
        ("APPLE", "APPLE"),
        ("ALPHABET INC CL A", "ALPHABET"),
        ("ALPHABET CLASS C", "ALPHABET"),
        ("META PLATFORMS INC-CLASS A", "METAPLATFORMS"),
        ("ELI LILLY & CO", "ELILILLY"),
        ("Eli Lilly and Company", "ELILILLY"),
        ("AT&T INC", "ATT"),
        ("O'REILLY AUTOMOTIVE INC", "OREILLYAUTOMOTIVE"),
        ("ROCHE GENUSSS CHF", "ROCHE"),
        ("TEXAS INSTRUMENTS COM USD1", "TEXASINSTRUMENTS"),
        ("Société Générale SA", "SOCIETEGENERALE"),
        ("TJX COMPANIES INC", "TJX"),
        (None, ""),
    ],
)
def test_names_are_normalised(name, expected):
    assert normalise_name(name) == expected


def _lines(*rows):
    return pd.DataFrame(rows, columns=["name", "location", "issuer", "w", "security_isin"])


def test_same_name_different_writing_is_one_company():
    keys = company_keys(
        _lines(
            ("APPLE", "United States", "iShares", 0.05, None),
            ("Apple Inc.", "United States", "SPDR", 0.05, "US0378331005"),
        )
    )
    assert len(set(keys)) == 1


def test_same_isin_is_one_company_whatever_the_name():
    keys = company_keys(
        _lines(
            ("GE AEROSPACE", "United States", "Xtrackers", 0.01, "US3696043013"),
            ("GENERAL ELECTRIC CO", "United States", "Amundi", 0.01, "US3696043013"),
        )
    )
    assert len(set(keys)) == 1


def test_unique_prefix_across_issuers_in_the_same_country():
    keys = company_keys(
        _lines(
            ("APPLIED MATERIAL", "United States", "iShares", 0.01, None),
            ("APPLIED MATERIALS INC", "United States", "Amundi", 0.01, "US0382221051"),
            ("APPLIED MATERIAL", "Canada", "iShares", 0.01, None),  # other country: apart
        )
    )
    assert keys[0] == keys[1] != keys[2]


def test_country_disagreement_is_resolved_with_the_ishares_country():
    keys = company_keys(
        _lines(
            ("SHELL PLC", "United Kingdom", "iShares", 0.03, None),
            ("SHELL PLC", "Netherlands", "Xtrackers", 0.03, "GB00BP6MXD84"),
        )
    )
    assert set(keys) == {"SHELL|United Kingdom"}


def test_two_companies_with_one_name_in_one_issuer_are_never_merged():
    keys = company_keys(
        _lines(
            ("EQT", "Sweden", "iShares", 0.001, None),
            ("EQT CORP", "United States", "iShares", 0.001, None),
            ("EQT AB", "Sweden", "Xtrackers", 0.001, "SE0012853455"),
            ("EQT CORP", "United States", "Xtrackers", 0.001, "US26884L1098"),
        )
    )
    assert keys[0] == keys[2] != keys[1]
    assert keys[1] == keys[3]
