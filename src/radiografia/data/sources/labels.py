"""Issuers' labels translated to the ones the engine uses (those of iShares' English files).

Xtrackers and Amundi publish their Spanish files with Spanish country and sector names (and the
odd label in other languages: "Isole Cayman", "NEW_ZEALAND", "Materials"); SPDR writes countries
in English but not always as iShares does ("South Korea" vs "Korea (South)"). The engine and the
presentation layer (reporting/presentation.py) work with iShares' English labels, so every
reader maps to them here. A label that is not in these tables is kept as published: it shows up
as its own country or sector instead of being guessed.
"""

from __future__ import annotations

import unicodedata

_COUNTRIES = {
    # Spanish
    "estados unidos": "United States",
    "japon": "Japan",
    "canada": "Canada",
    "reino unido": "United Kingdom",
    "francia": "France",
    "alemania": "Germany",
    "suiza": "Switzerland",
    "suecia": "Sweden",
    "paises bajos": "Netherlands",
    "holanda": "Netherlands",
    "italia": "Italy",
    "espana": "Spain",
    "dinamarca": "Denmark",
    "singapur": "Singapore",
    "finlandia": "Finland",
    "noruega": "Norway",
    "irlanda": "Ireland",
    "belgica": "Belgium",
    "nueva zelanda": "New Zealand",
    "luxemburgo": "Luxembourg",
    "brasil": "Brazil",
    "emiratos arabes unidos": "United Arab Emirates",
    "macao": "Macau",
    "corea del sur": "Korea (South)",
    "corea": "Korea (South)",
    "tailandia": "Thailand",
    "islas caiman": "Cayman Islands",
    "isole cayman": "Cayman Islands",
    "bermudas": "Bermuda",
    "jersey": "Jersey",
    "guernsey": "Guernsey",
    "isla de man": "Isle of Man",
    "polonia": "Poland",
    "republica checa": "Czech Republic",
    "chequia": "Czech Republic",
    "hungria": "Hungary",
    "grecia": "Greece",
    "turquia": "Turkey",
    "rusia": "Russian Federation",
    "sudafrica": "South Africa",
    "arabia saudi": "Saudi Arabia",
    "arabia saudita": "Saudi Arabia",
    "catar": "Qatar",
    "kuwait": "Kuwait",
    "egipto": "Egypt",
    "marruecos": "Morocco",
    "mexico": "Mexico",
    "peru": "Peru",
    "colombia": "Colombia",
    "filipinas": "Philippines",
    "malasia": "Malaysia",
    "indonesia": "Indonesia",
    "india": "India",
    "taiwan": "Taiwan",
    "zambia": "Zambia",
    "union europea": "European Union",
    "supranacional": "Supranational",
    # English variants
    "south korea": "Korea (South)",
    "republic of korea": "Korea (South)",
    "korea": "Korea (South)",
    "russia": "Russian Federation",
    "new_zealand": "New Zealand",
    "czechia": "Czech Republic",
    "slovakia": "Slovak Republic",
    "croatia": "Croatia (Hrvatska)",
    "none": "-",
}

_SECTORS = {
    "industrial": "Industrials",
    "industriales": "Industrials",
    "finanzas": "Financials",
    "financieros": "Financials",
    "tecnologias de la informacion": "Information Technology",
    "tecnologia de la informacion": "Information Technology",
    "consumo discrecional": "Consumer Discretionary",
    "salud": "Health Care",
    "atencion sanitaria": "Health Care",
    "materiales": "Materials",
    "productos de primera necesidad": "Consumer Staples",
    "productos basicos de consumo": "Consumer Staples",
    "consumo basico": "Consumer Staples",
    "servicios de utilidad publica": "Utilities",
    "servicios publicos": "Utilities",
    "servicios de comunicacion": "Communication",
    "communication services": "Communication",
    "bienes inmobiliarios": "Real Estate",
    "inmobiliario": "Real Estate",
    "energia": "Energy",
    "desconocido": None,
    "unassigned": None,
}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def country(label: object) -> object:
    if not isinstance(label, str) or not label.strip():
        return None
    return _COUNTRIES.get(_plain(label), label.strip())


def sector(label: object) -> object:
    if not isinstance(label, str) or not label.strip():
        return None
    plain = _plain(label)
    return _SECTORS[plain] if plain in _SECTORS else label.strip()
