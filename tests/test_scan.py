"""offline: log decoding, chunking, labels, pricing, and the table with a fake node."""
import json

from bigmoves import cli, labels, prices, scan, tokens
from bigmoves.labels import Labeler, short
from bigmoves.scan import Move, chunks, decode_block, decode_log
from bigmoves.tokens import ETH, TOKENS, TRANSFER_TOPIC, by_address, pick

BINANCE_14 = "0x28c6c06298d514db089934071355e5743bf21d60"
SOMEONE = "0x" + "ab" * 20


def topic(address):
    return "0x" + "0" * 24 + address[2:].lower()


def log(token, sender, receiver, raw, block=100, index=7):
    return {
        "address": token.address, "topics": [TRANSFER_TOPIC, topic(sender), topic(receiver)],
        "data": "0x" + hex(raw)[2:].rjust(64, "0"), "blockNumber": hex(block), "transactionHash": "0x" + "11" * 32,
        "logIndex": hex(index),
    }


def test_chunks_are_inclusive_and_cover_the_range():
    assert chunks(100, 160, 25) == [(100, 124), (125, 149), (150, 160)]
    assert chunks(5, 5, 25) == [(5, 5)]
    assert chunks(10, 9, 25) == []


def test_decode_transfer_log():
    usdt = TOKENS["USDT"]
    m = decode_log(log(usdt, BINANCE_14, SOMEONE, 12_500_000 * 10**6), by_address([usdt]))
    assert m.token is usdt and m.amount == 12_500_000 and m.sender == BINANCE_14 and m.receiver == SOMEONE
    assert m.block == 100 and m.log_index == 7


def test_decode_ignores_other_tokens_and_short_topics():
    usdt = TOKENS["USDT"]
    assert decode_log(log(TOKENS["USDC"], BINANCE_14, SOMEONE, 1), by_address([usdt])) is None
    bad = log(usdt, BINANCE_14, SOMEONE, 1)
    bad["topics"] = bad["topics"][:2]
    assert decode_log(bad, by_address([usdt])) is None


def test_decode_block_keeps_only_big_value_transfers():
    block = {"number": "0x64", "transactions": [
        {"hash": "0xa", "from": BINANCE_14, "to": SOMEONE, "value": hex(3000 * 10**18)},
        {"hash": "0xb", "from": SOMEONE, "to": BINANCE_14, "value": hex(1 * 10**18)},
        {"hash": "0xc", "from": SOMEONE, "to": None, "value": hex(5000 * 10**18)},  # contract creation
    ]}
    found = decode_block(block, min_wei=2000 * 10**18)
    assert [m.tx for m in found] == ["0xa"] and found[0].token is ETH and found[0].amount == 3000


def test_pick_tokens():
    assert [t.symbol for t in pick(None)] == ["USDT", "USDC", "DAI", "WETH", "WBTC"]
    assert [t.symbol for t in pick("wbtc, link")] == ["WBTC", "LINK"]
    try:
        pick("DOGE")
        assert False, "should raise"
    except KeyError:
        pass


def test_prices_and_threshold():
    table = {"ethereum": 2500.0}
    assert prices.usd_value(TOKENS["USDC"], 5.0, table) == 5.0
    assert prices.usd_value(TOKENS["WETH"], 2.0, table) == 5000.0
    assert prices.usd_value(TOKENS["WBTC"], 2.0, table) is None
    moves = [Move(1, "0x1", TOKENS["USDT"], 2e6, SOMEONE, SOMEONE), Move(1, "0x2", TOKENS["WBTC"], 100, SOMEONE, SOMEONE),
             Move(1, "0x3", TOKENS["WETH"], 1000, SOMEONE, SOMEONE), Move(1, "0x4", TOKENS["DAI"], 10, SOMEONE, SOMEONE)]
    kept = cli.keep(cli.priced(moves, table), 1e6)
    assert [m.tx for m in kept] == ["0x3", "0x1"]  # wbtc unpriced -> dropped, dai too small


def test_labels_builtin_and_extra(tmp_path):
    built = labels.builtin()
    assert built[BINANCE_14].startswith("binance")
    extra = tmp_path / "mine.json"
    extra.write_text(json.dumps({SOMEONE: "my cold wallet"}), encoding="utf-8")
    merged = labels.load(str(extra))
    who = Labeler(merged)
    assert who.name(SOMEONE) == "my cold wallet" and who.name(labels.ZERO) == "0x0 (mint or burn)"
    assert who.name("0x" + "cd" * 20) == short("0x" + "cd" * 20) == "0xcdcd..cdcd"


def test_labeler_uses_ens_only_when_verified():
    class FakeEns:
        def reverse(self, address):
            return ("whale.eth", True) if address.lower() == SOMEONE else ("liar.eth", False)

    who = Labeler(labels.load(), FakeEns())
    assert who.name(SOMEONE) == "whale.eth"
    assert who.name("0x" + "cd" * 20) == "0xcdcd..cdcd"


def test_money_and_amount_formatting():
    assert cli.money(12_500_000) == "$12.5m" and cli.money(2.3e9) == "$2.30b" and cli.money(950_000) == "$950k"
    assert cli.amount(12_500_000) == "12,500,000" and cli.amount(3.14159) == "3.14"


def test_cli_table_with_fake_node(monkeypatch, capsys):
    usdt = TOKENS["USDT"]

    class FakeRpc:
        def __init__(self, urls=None):
            pass

        def block_number(self):
            return 199

        def call(self, method, params):
            assert method == "eth_getLogs"
            lo, hi = int(params[0]["fromBlock"], 16), int(params[0]["toBlock"], 16)
            found = [log(usdt, BINANCE_14, SOMEONE, 12_500_000 * 10**6, block=150),
                     log(usdt, SOMEONE, BINANCE_14, 1_000 * 10**6, block=151)]
            return [entry for entry in found if lo <= int(entry["blockNumber"], 16) <= hi]

    monkeypatch.setattr(cli, "Rpc", FakeRpc)
    monkeypatch.setattr(cli, "fetch_prices", lambda tokens: {})
    assert cli.main(["--blocks", "50", "--tokens", "USDT"]) == 0
    out = capsys.readouterr().out
    assert "$12.5m" in out and "binance 14" in out and "0xabab..abab" in out and "#150" in out
    assert "1 transfers in blocks 150-199" in out
    assert cli.main(["--blocks", "50", "--tokens", "USDT", "--json"]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    assert line["usd"] == 12_500_000 and line["from_label"] == "binance 14" and line["to_label"] is None
    assert line["etherscan"].startswith("https://etherscan.io/tx/0x")


def test_cli_rejects_unknown_token():
    assert cli.main(["--tokens", "DOGE"]) == 2
