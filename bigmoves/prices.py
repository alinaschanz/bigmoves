"""usd prices from coingecko's public endpoint. no key, so be gentle: one call per run."""
from __future__ import annotations

import json
import urllib.request

from .tokens import Token

USER_AGENT = "bigmoves/0.1 (+https://github.com/alinaschanz/bigmoves)"


def fetch_prices(tokens: list[Token], timeout: float = 15.0) -> dict[str, float]:
    """coingecko id -> usd. stables are not fetched, they are a dollar by definition here."""
    ids = sorted({t.coingecko for t in tokens if t.coingecko})
    if not ids:
        return {}
    url = "https://api.coingecko.com/api/v3/simple/price?ids=" + ",".join(ids) + "&vs_currencies=usd"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return {k: float(v["usd"]) for k, v in body.items() if "usd" in v}


def usd_value(token: Token, amount: float, prices: dict[str, float]) -> float | None:
    if token.stable:
        return amount
    price = prices.get(token.coingecko or "")
    return None if price is None else amount * price
