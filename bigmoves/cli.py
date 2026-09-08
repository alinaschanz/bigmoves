"""command line entry point: bigmoves [--blocks 50] [--min-usd 1000000] [--follow]"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

from . import __version__
from .labels import DEAD, ZERO, Labeler, load
from .prices import fetch_prices, usd_value
from .rpc import Rpc, RpcError, RpcUnavailable
from .scan import Move, block_at, parse_duration, scan_eth, scan_tokens
from .tokens import TOKENS, pick

ETHERSCAN_TX = "https://etherscan.io/tx/"


def money(value: float | None) -> str:
    if value is None:
        return "?"
    if value >= 1e9:
        return f"${value / 1e9:.2f}b"
    if value >= 1e6:
        return f"${value / 1e6:.1f}m"
    if value >= 1e3:
        return f"${value / 1e3:.0f}k"
    return f"${value:.0f}"


def amount(value: float) -> str:
    if value >= 1e6:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def priced(moves: list[Move], prices: dict[str, float]) -> list[Move]:
    for m in moves:
        m.usd = usd_value(m.token, m.amount, prices)
    return moves


def keep(moves: list[Move], min_usd: float) -> list[Move]:
    """largest first; unpriced tokens are dropped rather than guessed."""
    out = [m for m in moves if m.usd is not None and m.usd >= min_usd]
    out.sort(key=lambda m: -m.usd)  # type: ignore[operator]
    return out


def group(moves: list[Move]) -> list[Move]:
    """fold what belongs together inside one transaction.

    the same token going a -> b and b -> a in one tx (a flash loan, a wrap and unwrap) becomes
    one line tagged `round trip`; a transfer from 0x0 is a `mint`, one to 0x0 or 0xdead a `burn`.
    order is kept: the first leg of a pair stays where it was.
    """
    by_tx: dict[str, list[Move]] = defaultdict(list)
    for m in moves:
        by_tx[m.tx].append(m)
    folded: set[tuple[str, int]] = set()
    for legs in by_tx.values():
        for i, a in enumerate(legs):
            if a.key in folded:
                continue
            for b in legs[i + 1:]:
                same_pair = b.token is a.token and b.sender == a.receiver and b.receiver == a.sender
                if b.key not in folded and same_pair and abs(b.amount - a.amount) <= 1e-9 * max(a.amount, 1.0):
                    a.tag = "round trip"
                    folded.add(b.key)
                    break
            else:
                if a.sender.lower() == ZERO:
                    a.tag = "mint"
                elif a.receiver.lower() in (ZERO, DEAD):
                    a.tag = "burn"
    return [m for m in moves if m.key not in folded]


def row(m: Move, who: Labeler, links: bool) -> str:
    tx = ETHERSCAN_TX + m.tx if links else m.tx[:10] + ".." + m.tx[-4:]
    tag = f"  [{m.tag}]" if m.tag else ""
    return (f"{money(m.usd):>8}  {m.token.symbol:<5} {amount(m.amount):>16}  "
            f"{who.name(m.sender):<26} -> {who.name(m.receiver):<26} #{m.block}  {tx}{tag}")


def to_json(m: Move, who: Labeler) -> dict:
    return {
        "block": m.block, "tx": m.tx, "token": m.token.symbol, "amount": m.amount, "usd": m.usd,
        "from": m.sender, "from_label": who.name(m.sender) if who.is_labeled(m.sender) else None,
        "to": m.receiver, "to_label": who.name(m.receiver) if who.is_labeled(m.receiver) else None,
        "etherscan": ETHERSCAN_TX + m.tx, "tag": m.tag or None,
    }


def scan_range(rpc: Rpc, args, tokens, prices, from_block: int, to_block: int) -> list[Move]:
    moves = scan_tokens(rpc, tokens, from_block, to_block, chunk=args.chunk)
    if args.eth:
        eth_price = prices.get("ethereum")
        if eth_price:
            moves += scan_eth(rpc, from_block, to_block, min_eth=args.min_usd / eth_price)
        else:
            print("warning: no eth price, skipping plain eth transfers", file=sys.stderr)
    kept = keep(priced(moves, prices), args.min_usd)
    return kept if args.raw else group(kept)


def summary(moves: list[Move], from_block: int, to_block: int) -> str:
    n_blocks = to_block - from_block + 1
    total = sum(m.usd or 0 for m in moves)
    per_token: dict[str, float] = {}
    for m in moves:
        per_token[m.token.symbol] = per_token.get(m.token.symbol, 0) + (m.usd or 0)
    parts = ", ".join(f"{k} {money(v)}" for k, v in sorted(per_token.items(), key=lambda kv: -kv[1]))
    return (f"{len(moves)} transfers in blocks {from_block:,}-{to_block:,} ({n_blocks} blocks, ~{n_blocks * 12 // 60} min): "
            f"{money(total)} total" + (f" ({parts})" if parts else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bigmoves", description="large erc-20 and eth transfers on ethereum mainnet, from a public rpc.")
    ap.add_argument("--blocks", type=int, default=50, help="how many recent blocks to scan (default 50, about 10 minutes)")
    ap.add_argument("--since", metavar="1h", help="scan this much time instead of a block count: 30m, 1h, 2d (a few header lookups)")
    ap.add_argument("--min-usd", type=float, default=1_000_000, help="threshold in usd (default 1,000,000)")
    ap.add_argument("--tokens", metavar="SYMBOLS", help=f"comma separated, from: {', '.join(TOKENS)} (default USDT,USDC,DAI,WETH,WBTC)")
    ap.add_argument("--eth", action="store_true", help="also plain eth transfers (needs full blocks, slower)")
    ap.add_argument("--follow", action="store_true", help="keep watching new blocks until ctrl-c")
    ap.add_argument("--json", action="store_true", help="json lines instead of the table")
    ap.add_argument("--links", action="store_true", help="full etherscan links instead of short tx hashes")
    ap.add_argument("--labels", metavar="FILE", help="json file {address: label} merged over the built-in list")
    ap.add_argument("--ens", action="store_true", help="reverse-resolve unlabeled addresses with the enslookup package")
    ap.add_argument("--rpc", action="append", metavar="URL", help="json-rpc endpoint (repeatable, tried in order)")
    ap.add_argument("--chunk", type=int, default=25, help="blocks per eth_getLogs call (public nodes cap this, default 25)")
    ap.add_argument("--no-price", action="store_true", help="skip coingecko; only stablecoins get a usd value")
    ap.add_argument("--raw", action="store_true", help="every transfer on its own line: no round-trip folding, no mint/burn tags")
    ap.add_argument("--version", action="version", version=f"bigmoves {__version__}")
    args = ap.parse_args(argv)

    try:
        tokens = pick(args.tokens)
    except KeyError as exc:
        print(f"error: unknown token {exc}, pick from {', '.join(TOKENS)}", file=sys.stderr)
        return 2
    ens = None
    if args.ens:
        try:
            from enslookup import Ens  # optional: github.com/alinaschanz/ens-lookup
        except ImportError:
            print("error: --ens needs the enslookup package (pip install git+https://github.com/alinaschanz/ens-lookup)", file=sys.stderr)
            return 2
        ens = Ens()
    who = Labeler(load(args.labels), ens)
    rpc = Rpc(args.rpc) if args.rpc else Rpc()
    prices: dict[str, float] = {}
    if not args.no_price:
        try:
            prices = fetch_prices(tokens + ([TOKENS["WETH"]] if args.eth else []))
        except Exception as exc:
            print(f"warning: coingecko unavailable ({exc}); only stablecoins will be priced", file=sys.stderr)

    try:
        latest = rpc.block_number()
        if args.since:
            try:
                seconds = parse_duration(args.since)
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            latest_ts = rpc.block_timestamp(latest)
            from_block, to_block = block_at(rpc, latest, latest_ts - seconds, latest_ts), latest
        else:
            from_block, to_block = max(0, latest - args.blocks + 1), latest
        moves = scan_range(rpc, args, tokens, prices, from_block, to_block)
        emit(moves, who, args)
        if not args.json:
            print(summary(moves, from_block, to_block))
        if not args.follow:
            return 0
        seen = to_block
        while True:
            time.sleep(12)
            latest = rpc.block_number()
            if latest <= seen:
                continue
            fresh = scan_range(rpc, args, tokens, prices, seen + 1, latest)
            if fresh:
                stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                if not args.json:
                    print(f"-- {stamp} utc, blocks {seen + 1:,}-{latest:,}")
                emit(fresh, who, args)
            seen = latest
    except (RpcError, RpcUnavailable) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


def emit(moves: list[Move], who: Labeler, args) -> None:
    for m in moves:
        print(json.dumps(to_json(m, who)) if args.json else row(m, who, args.links))
    sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
