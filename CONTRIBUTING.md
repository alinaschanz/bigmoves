# contributing

the most useful thing you can send is a label with a source.

## adding a label

`bigmoves/labels.json` maps a lowercase address to a short lowercase label:

```json
"0x28c6c06298d514db089934071355e5743bf21d60": "binance 14"
```

rules, so the list stays worth trusting:

- one address per line, lowercase, keep the file sorted by label (the test does not check
  order, people reading diffs do).
- in the pull request, say where the label comes from: a block explorer tag, an exchange
  proof-of-reserves page, an official announcement. "everyone knows" is not a source.
- exchanges get the explorer's numbering (`kraken 4`), protocols get `project: thing`
  (`aave v3: pool`), defunct ones get `(defunct)`.
- no guesses from transaction patterns alone. a wallet that talks to binance is not binance.

## code

- python 3.10+, standard library only. a dependency needs a very good reason.
- `python -m pytest -q` must pass offline. `BIGMOVES_LIVE=1 python -m pytest -q` talks to a
  public rpc and checks the token table against the chain; run it once before you send
  anything that touches `tokens.py`.
- `ruff check .` with the settings in `pyproject.toml`.
- keep the output stable: scripts parse it.

## what i will say no to

api keys, paid data sources, and anything that turns "large transfers" into "buy signals".
numbers, not calls.
