"""talks to a public rpc. skipped unless BIGMOVES_LIVE=1."""
import os

import pytest

from bigmoves.rpc import Rpc
from bigmoves.scan import scan_tokens
from bigmoves.tokens import TOKENS

pytestmark = pytest.mark.skipif(os.environ.get("BIGMOVES_LIVE") != "1", reason="set BIGMOVES_LIVE=1")

SEL_SYMBOL = "0x95d89b41"
SEL_DECIMALS = "0x313ce567"


def read_string(hexdata: str) -> str:
    data = bytes.fromhex(hexdata[2:])
    if len(data) == 32:  # a few old tokens return bytes32
        return data.rstrip(b"\x00").decode()
    offset = int.from_bytes(data[:32], "big")
    length = int.from_bytes(data[offset:offset + 32], "big")
    return data[offset + 32:offset + 32 + length].decode()


def test_token_table_matches_the_chain():
    rpc = Rpc()
    for token in TOKENS.values():
        symbol = read_string(rpc.call("eth_call", [{"to": token.address, "data": SEL_SYMBOL}, "latest"]))
        decimals = int(rpc.call("eth_call", [{"to": token.address, "data": SEL_DECIMALS}, "latest"]), 16)
        assert symbol == token.symbol, (token.symbol, symbol)
        assert decimals == token.decimals, (token.symbol, decimals)


def test_recent_blocks_have_stablecoin_transfers():
    rpc = Rpc()
    latest = rpc.block_number()
    moves = scan_tokens(rpc, [TOKENS["USDT"], TOKENS["USDC"]], latest - 9, latest, chunk=10)
    assert moves and all(m.amount >= 0 for m in moves)
