"""Recognise the same company in the holdings of different issuers.

Each issuer writes company names its own way ("APPLE", "APPLE INC", "Apple Inc.") and only some
publish the ISIN of each position (iShares does not). Within one issuer the engine keeps its
original rule (name without share-class suffix + country, validated against the issuer). When a
portfolio mixes issuers, a company is identified by a key built with four rules, in order:

1. Normalised name: accents, punctuation, spaces, legal forms (INC, CORP, PLC, AG...),
   share-class markers (CLASS A, CL A, PS PAR...) and listing noise (currency codes, exchange
   names) are removed: "Apple Inc." and "APPLE" both become "APPLE". The key is that name plus
   the country.
2. Same ISIN, same company: lines that publish the same security ISIN share one key.
3. Prefix: across issuers, in the same country, a name that is the only one starting with
   another of at least 6 letters is the same company ("APPLIEDMATERIAL" / "APPLIEDMATERIALS").
4. Country: issuers do not always agree on a company's country (Shell: United Kingdom for
   iShares, Netherlands for Xtrackers). A name found in a single country in each issuer's files
   is one company even if those countries differ; it takes the country iShares gives (else the
   one with the most weight). A name with several countries within one issuer (EQT of Sweden and
   EQT of the US) is never merged this way.

Renamed or abbreviated companies ("GENERAL ELECTRIC" / "GE AEROSPACE") stay as two keys, which
slightly understates the overlap between funds of different issuers. The share of weight
matched is measured in docs/VALIDACION.md.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

import pandas as pd

_NOISE = (
    r"INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|COMPANIES|COS|PLC|LTD|LIMITED|LLC|LP|"
    r"AG|SA|S A|NV|N V|SE|SPA|S P A|AB|ASA|A S|AS|OYJ|KK|TBK|BHD|PCL|SAB|DE CV|THE|AND|"
    r"HOLDINGS?|HLDGS?|GROUP|GRP|"
    r"CLASS [A-Z]|CL [A-Z]|SERIES [A-Z]|SER [A-Z]|"
    r"REG|REGISTERED|ORD|ORDINARY|SHS|SHARES|NPV|PREF|PFD|ADR|GDR|NON VTG|PS PAR|GENUSSS?|"
    r"COM|USD1|USD|EUR|GBP|GBX|CHF|JPY|CAD|AUD|HKD|SEK|NOK|DKK|SGD|XETRA"
)
_NOISE_WORD = re.compile(rf"\b(?:{_NOISE})\b")
_TRAILING_CLASS = re.compile(r"(?: [A-Z])+$")
_JOINED_AMPERSAND = re.compile(r"(?<=[A-Z])&(?=[A-Z])")
_NOT_ALNUM = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")
MIN_PREFIX = 6
PREFERRED_ISSUER = "iShares"  # its names and countries are the ones validated against the issuer


def normalise_name(name: object) -> str:
    """'Apple Inc.' -> 'APPLE'; 'ALPHABET INC CL A' -> 'ALPHABET'; 'AT&T INC' -> 'ATT'."""
    if not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    text = _JOINED_AMPERSAND.sub("", text.replace("'", ""))
    text = _NOT_ALNUM.sub(" ", text.replace("&", " AND "))
    text = _SPACES.sub(" ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = _SPACES.sub(" ", _NOISE_WORD.sub(" ", text)).strip()
        text = _TRAILING_CLASS.sub("", text) if len(text) > 3 else text
    return text.replace(" ", "")


def company_keys(lines: pd.DataFrame) -> pd.Series:
    """Key of each line ("NAME|Country"). `lines` needs name, location, issuer and w (weight);
    security_isin is used when present."""
    names = lines["name"].map(normalise_name)
    country = lines["location"].fillna("-").astype(str)
    issuer = lines["issuer"].fillna("").astype(str)
    keys = names + "|" + country

    # rule 2: one key per published security ISIN (the most common one among its lines)
    if "security_isin" in lines:
        isin = lines["security_isin"]
        with_isin = isin.notna() & (isin.astype(str) != "")
        if with_isin.any():
            chosen = keys[with_isin].groupby(isin[with_isin]).agg(lambda s: s.mode().iloc[0])
            keys = keys.where(~with_isin, isin.map(chosen))

    # rule 3: unique prefix across issuers, same country
    issuers_of: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for key, who in zip(keys, issuer, strict=True):
        name, where = key.rsplit("|", 1)
        issuers_of[where][name].add(who)
    mapping: dict[str, str] = {}
    for where, by_name in issuers_of.items():
        ordered = sorted(by_name)
        for short in ordered:
            if len(short) < MIN_PREFIX:
                continue
            longer = [
                n
                for n in ordered
                if n != short and n.startswith(short) and not (by_name[n] & by_name[short])
            ]
            if len(longer) == 1:
                mapping.setdefault(f"{longer[0]}|{where}", f"{short}|{where}")
    keys = keys.map(lambda k: mapping.get(k, k))

    # rule 4: same name, one country per issuer, different countries across issuers
    frame = pd.DataFrame(
        {"key": keys, "issuer": issuer, "w": lines["w"].fillna(0.0).to_numpy()}, index=keys.index
    )
    frame["name"] = frame["key"].str.rsplit("|", n=1).str[0]
    frame["country"] = frame["key"].str.rsplit("|", n=1).str[1]
    per_issuer = frame.groupby(["name", "issuer"])["country"].nunique()
    single = per_issuer.groupby(level="name").max() == 1
    spread = frame.groupby("name")["country"].nunique() > 1  # noqa: PD101
    for name in single[single & spread].index:
        rows = frame[frame["name"] == name]
        preferred = rows[rows["issuer"] == PREFERRED_ISSUER]
        source = preferred if not preferred.empty else rows
        where = source.groupby("country")["w"].sum().idxmax()
        keys[rows.index] = f"{name}|{where}"
    return keys
