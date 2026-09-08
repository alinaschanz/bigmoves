# changelog

all notable changes to bigmoves. the format follows [keep a changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [semver](https://semver.org/) as far as a command line tool has an api.

## [unreleased]

- `--since 1h`: time windows, found by bisecting block headers

- round trips inside one transaction fold into one line tagged `[round trip]`; `[mint]` and `[burn]` tags; `--raw` for every leg

## [0.1.0] - 2026-09-08

first cut: large erc-20 and eth transfers with exchange and bridge labels.

- `Transfer` events of the big tokens from the last n blocks, priced and filtered
- about 290 exchange, bridge, router and treasury labels; `--labels`, `--ens`
- `--follow`, `--eth`, `--json`
