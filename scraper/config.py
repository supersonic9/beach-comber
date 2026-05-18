import os

BASE_URL = "https://casa.sapo.pt/comprar-{prop_type}/{area}/"

AREAS: dict[str, str] = {
    "povoa-de-varzim": "Póvoa de Varzim",
    "vila-do-conde": "Vila do Conde",
    "matosinhos": "Matosinhos",
    "vila-nova-de-gaia": "Vila Nova de Gaia",
}

PROPERTY_TYPES: list[str] = [
    "apartamentos",
    "moradias",
    "terrenos",
    "lojas",
    "escritorios",
    "predios",
    "armazens",
    "quintas-e-herdades",
    "garagens",
    "luxo",
]

REQUEST_DELAY_MIN: float = float(os.environ.get("REQUEST_DELAY_MIN", "1.5"))
REQUEST_DELAY_MAX: float = float(os.environ.get("REQUEST_DELAY_MAX", "3.5"))
