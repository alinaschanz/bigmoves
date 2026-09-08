"""who is that address? a small hand-kept list of exchange and protocol addresses,
plus anything the user passes in with --labels."""
from __future__ import annotations

import json
from importlib import resources

ZERO = "0x" + "0" * 40
DEAD = "0x000000000000000000000000000000000000dead"


def builtin() -> dict[str, str]:
    raw = json.loads(resources.files(__package__).joinpath("labels.json").read_text(encoding="utf-8"))
    return {k.lower(): v for k, v in raw.items()}


def load(extra_path: str | None = None) -> dict[str, str]:
    labels = builtin()
    if extra_path:
        with open(extra_path, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                labels[k.lower()] = str(v)
    labels.setdefault(ZERO, "0x0 (mint or burn)")
    labels.setdefault(DEAD, "burn address")
    return labels


def short(address: str) -> str:
    return address[:6] + ".." + address[-4:]


class Labeler:
    """labels first, then an optional ens reverse lookup, then the short form."""

    def __init__(self, labels: dict[str, str], ens=None):
        self.labels = labels
        self.ens = ens
        self._ens_cache: dict[str, str | None] = {}

    def name(self, address: str) -> str:
        key = address.lower()
        if key in self.labels:
            return self.labels[key]
        if self.ens is not None:
            if key not in self._ens_cache:
                try:
                    name, verified = self.ens.reverse(address)
                except Exception:  # noqa: BLE001 - a flaky rpc must not kill the table
                    name, verified = None, None
                self._ens_cache[key] = name if verified else None
            if self._ens_cache[key]:
                return self._ens_cache[key]
        return short(address)

    def is_labeled(self, address: str) -> bool:
        return address.lower() in self.labels
