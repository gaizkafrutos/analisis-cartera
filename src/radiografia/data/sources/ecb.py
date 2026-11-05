"""European Central Bank: euro foreign exchange reference rates (series EXR).

Reuse is free with attribution ("Fuente: BCE"); modified data must say so (we convert NAVs to
euros). See docs/FUENTES_Y_LICENCIAS.md. Rates are published around 14:15 CET on TARGET business
days, as units of foreign currency per 1 EUR (e.g. 1.1355 USD per EUR).

Only `fetch_exr_csv` touches the network, and it is only called from scripts/.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date

import pandas as pd

_EXR_URL = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
    "?format=csvdata&startPeriod={start}&endPeriod={end}"
)
_USER_AGENT = "radiografia-cartera/0.1 (personal educational project)"


class EcbFormatError(ValueError):
    pass


def exr_url(currency: str, start: date, end: date) -> str:
    return _EXR_URL.format(currency=currency, start=start.isoformat(), end=end.isoformat())


def fetch_exr_csv(currency: str, start: date, end: date, timeout: float = 120) -> str:
    request = urllib.request.Request(
        exr_url(currency, start, end), headers={"User-Agent": _USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_exr_csv(text: str) -> pd.Series:
    """ECB SDMX CSV -> Series of rates (foreign currency per EUR) indexed by date."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "TIME_PERIOD" not in rows[0] or "OBS_VALUE" not in rows[0]:
        raise EcbFormatError("unexpected ECB CSV: TIME_PERIOD/OBS_VALUE columns not found")
    values = {
        pd.Timestamp(row["TIME_PERIOD"]): float(row["OBS_VALUE"])
        for row in rows
        if row["OBS_VALUE"] not in ("", "NaN")
    }
    if not values:
        raise EcbFormatError("ECB CSV has no observations")
    return pd.Series(values, name="rate").sort_index()
