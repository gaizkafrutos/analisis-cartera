"""Build the public dataset (data/public/) from SEC Form N-PORT filings. Committed: public data.

Each UCITS ETF in data/reference/twins.csv is paired with the US ETF that tracks the same index
(pairs with a merely similar index are documented there but not used). For every twin, this
script downloads its N-PORT filings from SEC EDGAR:
    - the latest one: full holdings, used as the UCITS ETF's composition (labelled as such);
    - the recent ones: monthly total returns (for the risk section, next phase).

SEC fair-access policy: at most 10 requests per second and a User-Agent that identifies who is
asking, with a contact e-mail. Set it before running (it is not stored in the repository):

    $env:SEC_USER_AGENT = "Nombre Apellido tu@correo"      # PowerShell
    .venv\\Scripts\\python scripts\\build_public.py

Output: data/public/snapshots/<download date>/ with holdings.csv.gz, manifest.csv,
breakdowns.csv (empty), proxies.csv (which twin and filing each UCITS ETF uses) and
twin_returns.csv.
"""

from __future__ import annotations

import csv
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pandas as pd

from radiografia.data.snapshots import BREAKDOWNS_FILE, HOLDINGS_FILE, MANIFEST_FILE, PROXIES_FILE
from radiografia.data.sources import sec_nport

ROOT = Path(__file__).resolve().parents[1]
TWINS_FILE = ROOT / "data" / "reference" / "twins.csv"
PUBLIC_DIR = ROOT / "data" / "public"
RETURNS_FILE = "twin_returns.csv"
EDGAR = "https://www.sec.gov"
PAUSE_SECONDS = 0.25  # well under the 10 requests per second the SEC allows
FILINGS_FOR_RETURNS = 30  # each filing has 3 months of returns: enough for 5+ years
ATOM = {"a": "http://www.w3.org/2005/Atom"}
USED_MATCHES = {"exact"}


def user_agent() -> str:
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in value:
        sys.exit(
            "Set SEC_USER_AGENT to a name and contact e-mail, e.g. 'Ana Pérez ana@example.com'.\n"
            "The SEC rejects automated requests without one (fair access policy)."
        )
    return value


def get(url: str, agent: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": agent, "Accept-Encoding": "identity"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    time.sleep(PAUSE_SECONDS)
    return data


def filing_documents(series_id: str, agent: str, count: int) -> list[tuple[str, str]]:
    """(filing date, primary_doc.xml URL) of the latest NPORT-P filings, newest first."""
    feed = get(
        f"{EDGAR}/cgi-bin/browse-edgar?action=getcompany&CIK={series_id}&type=NPORT-P"
        f"&dateb=&owner=include&count={count}&output=atom",
        agent,
    )
    root = ET.fromstring(feed)
    documents = []
    for entry in root.iterfind("a:entry", ATOM):
        content = entry.find("a:content", ATOM)
        filed = content.findtext("a:filing-date", namespaces=ATOM) if content is not None else None
        href = content.findtext("a:filing-href", namespaces=ATOM) if content is not None else None
        kind = content.findtext("a:filing-type", namespaces=ATOM) if content is not None else None
        if filed and href and kind == "NPORT-P":
            documents.append((filed, href.rsplit("/", 1)[0] + "/primary_doc.xml"))
    return documents


def read_twins() -> list[dict[str, str]]:
    """Only twins that track exactly the same index: with a merely similar index the error was
    too large to call it an approximation (Japan: 67 effective companies against 104; US
    technology: 16 against 8; see docs/VALIDACION.md). They stay in twins.csv, documented."""
    with TWINS_FILE.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["match"] in USED_MATCHES]


def main() -> int:
    agent = user_agent()
    twins = read_twins()
    series = {row["sec_series_id"]: row for row in twins}

    latest: dict[str, tuple[sec_nport.NportFiling, str]] = {}
    returns = []
    for series_id, twin in series.items():
        documents = filing_documents(series_id, agent, FILINGS_FOR_RETURNS)
        if not documents:
            print(f"  {twin['us_ticker']}: no NPORT-P filings found", file=sys.stderr)
            continue
        for index, (_, url) in enumerate(documents):
            filing = sec_nport.parse_nport(get(url, agent))
            if index == 0:
                latest[series_id] = (filing, url)
                print(
                    f"  {twin['us_ticker']:5} {filing.series_name} - holdings at "
                    f"{filing.report_date} ({len(filing.holdings)} lines)"
                )
            own_class = filing.monthly_returns["class_id"] == twin["sec_class_id"]
            returns.append(filing.monthly_returns[own_class].assign(sec_series_id=series_id))

    lines, manifest, proxies = [], [], []
    for twin in twins:
        if twin["sec_series_id"] not in latest:
            continue
        filing, url = latest[twin["sec_series_id"]]
        lines.append(filing.holdings.assign(isin=twin["ucits_isin"]))
        manifest.append(
            {
                "isin": twin["ucits_isin"],
                "holdings_as_of": filing.report_date,
                "lines": len(filing.holdings),
            }
        )
        proxies.append(
            {
                "isin": twin["ucits_isin"],
                "ucits_index": twin["ucits_index"],
                "us_ticker": twin["us_ticker"],
                "us_name": twin["us_name"],
                "us_index": twin["us_index"],
                "match": twin["match"],
                "note": twin["note"],
                "sec_series_id": twin["sec_series_id"],
                "series_name_in_filing": filing.series_name,
                "report_date": filing.report_date,
                "filing_url": url,
            }
        )
    if not lines:
        sys.exit("nothing downloaded")

    holdings = sec_nport.harmonise_companies(pd.concat(lines, ignore_index=True))
    # security ISINs are only needed to read the filing: US ISINs embed the CUSIP, which has its
    # own licence, so the published file keeps names, LEIs and tickers but not ISINs
    holdings = holdings.drop(columns=["security_isin"])
    monthly = (
        pd.concat(returns, ignore_index=True)
        .drop_duplicates(["sec_series_id", "class_id", "month_end"], keep="first")
        .sort_values(["sec_series_id", "month_end"])
    )
    out = PUBLIC_DIR / "snapshots" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    gzip_no_time = {"method": "gzip", "mtime": 0}
    holdings.to_csv(out / HOLDINGS_FILE, index=False, lineterminator="\n", compression=gzip_no_time)
    pd.DataFrame(manifest).to_csv(out / MANIFEST_FILE, index=False, lineterminator="\n")
    pd.DataFrame(proxies).to_csv(out / PROXIES_FILE, index=False, lineterminator="\n")
    monthly.to_csv(out / RETURNS_FILE, index=False, lineterminator="\n")
    pd.DataFrame(columns=["section", "as_of", "label", "code", "weight", "isin"]).to_csv(
        out / BREAKDOWNS_FILE, index=False, lineterminator="\n"
    )
    print(f"{len(manifest)} UCITS ETFs from {len(latest)} US twins -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
