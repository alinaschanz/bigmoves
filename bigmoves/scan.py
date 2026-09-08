"""read transfer events (and optionally plain eth transfers) out of a block range."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .rpc import Rpc
from .tokens import ETH, TRANSFER_TOPIC, Token, by_address


@dataclass
class Move:
    block: int
    tx: str
    token: Token
    amount: float
    sender: str
    receiver: str
    log_index: int = 0
    usd: float | None = None
    tag: str = ""  # "round trip", "mint", "burn" once grouped; empty for a plain transfer

    @property
    def key(self) -> tuple[str, int]:
        return self.tx, self.log_index


def chunks(from_block: int, to_block: int, size: int) -> list[tuple[int, int]]:
    """inclusive (start, end) pairs of at most `size` blocks."""
    out = []
    start = from_block
    while start <= to_block:
        end = min(start + size - 1, to_block)
        out.append((start, end))
        start = end + 1
    return out


def topic_address(topic: str) -> str:
    return "0x" + topic[-40:]


def decode_log(log: dict, tokens: dict[str, Token]) -> Move | None:
    token = tokens.get(log["address"].lower())
    topics = log.get("topics") or []
    if token is None or len(topics) < 3 or topics[0] != TRANSFER_TOPIC:
        return None
    data = log.get("data") or "0x"
    if len(data) < 66:
        return None
    raw = int(data[2:66], 16)
    return Move(
        block=int(log["blockNumber"], 16),
        tx=log["transactionHash"],
        token=token,
        amount=raw / 10 ** token.decimals,
        sender=topic_address(topics[1]),
        receiver=topic_address(topics[2]),
        log_index=int(log.get("logIndex", "0x0"), 16),
    )


def scan_tokens(rpc: Rpc, tokens: list[Token], from_block: int, to_block: int, chunk: int = 25) -> list[Move]:
    lookup = by_address(tokens)
    addresses = [t.address for t in tokens]
    moves: list[Move] = []
    for start, end in chunks(from_block, to_block, chunk):
        logs = rpc.call("eth_getLogs", [{
            "fromBlock": hex(start), "toBlock": hex(end), "address": addresses, "topics": [TRANSFER_TOPIC],
        }]) or []
        for log in logs:
            if log.get("removed"):
                continue
            move = decode_log(log, lookup)
            if move is not None:
                moves.append(move)
    return moves


def decode_block(block: dict, min_wei: int) -> list[Move]:
    out = []
    number = int(block["number"], 16)
    for tx in block.get("transactions") or []:
        value = int(tx.get("value", "0x0"), 16)
        if value >= min_wei and tx.get("to"):
            out.append(Move(block=number, tx=tx["hash"], token=ETH, amount=value / 1e18,
                            sender=tx["from"], receiver=tx["to"], log_index=-1))
    return out


def scan_eth(rpc: Rpc, from_block: int, to_block: int, min_eth: float, workers: int = 3) -> list[Move]:
    """plain value transfers need the full blocks, which is the expensive part; keep the range small."""
    min_wei = int(min_eth * 1e18)

    def one(number: int) -> list[Move]:
        block = rpc.call("eth_getBlockByNumber", [hex(number), True])
        return decode_block(block, min_wei) if block else []

    moves: list[Move] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for found in pool.map(one, range(from_block, to_block + 1)):
            moves.extend(found)
    return moves
