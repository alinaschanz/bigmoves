"""a tiny json-rpc client over urllib with fallback across public endpoints."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_RPCS = (
    "https://ethereum-rpc.publicnode.com",
    "https://eth.drpc.org",
    "https://rpc.mevblocker.io",
    "https://gateway.tenderly.co/public/mainnet",
    "https://eth-mainnet.public.blastapi.io",
)
USER_AGENT = "bigmoves/0.1 (+https://github.com/alinaschanz/bigmoves)"


class RpcError(Exception):
    """the call itself failed (revert, bad params) - the same answer would come from every node."""


class RpcUnavailable(Exception):
    """no endpoint gave a usable answer."""


class Rpc:
    def __init__(self, urls: tuple[str, ...] | list[str] | None = None, timeout: float = 30.0):
        self.urls = list(urls or DEFAULT_RPCS)
        self.timeout = timeout
        self._id = 0

    def call(self, method: str, params: list):
        self._id += 1
        payload = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}).encode()
        last_problem: str | None = None
        for i, url in enumerate(list(self.urls)):
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read())
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                last_problem = f"{url}: {exc}"
                continue
            error = body.get("error") if isinstance(body, dict) else {"message": "malformed response"}
            if error:
                message = str(error.get("message", error)) if isinstance(error, dict) else str(error)
                if (isinstance(error, dict) and error.get("code") == 3) or "revert" in message.lower():
                    raise RpcError(message)
                last_problem = f"{url}: {message}"  # rate limit, range cap, internal error: next endpoint
                continue
            if i:  # remember the endpoint that worked, try it first next time
                try:
                    self.urls.remove(url)
                    self.urls.insert(0, url)
                except ValueError:
                    pass
            return body.get("result")
        raise RpcUnavailable(f"no rpc endpoint gave a usable answer ({last_problem})")

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)
