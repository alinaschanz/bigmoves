# bigmoves

[![ci](https://github.com/alinaschanz/bigmoves/actions/workflows/ci.yml/badge.svg)](https://github.com/alinaschanz/bigmoves/actions/workflows/ci.yml)
![python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)
![license mit](https://img.shields.io/badge/license-MIT-2b7a74)
[![release](https://img.shields.io/github/v/release/alinaschanz/bigmoves?color=2b7a74)](https://github.com/alinaschanz/bigmoves/releases)
[![openssf scorecard](https://api.scorecard.dev/projects/github.com/alinaschanz/bigmoves/badge)](https://scorecard.dev/viewer/?uri=github.com/alinaschanz/bigmoves)

large erc-20 and eth transfers on ethereum mainnet, from a public rpc, in your terminal.
no keys, nothing to install.

it reads the `Transfer` events of usdt, usdc, dai, weth and wbtc (more on request) out of
the last n blocks, prices them, keeps what is above a threshold and names the addresses it
knows: exchange wallets, bridges, routers, treasuries. `--follow` keeps watching.

```
$ bigmoves --blocks 50 --min-usd 1000000
  $26.1m  WETH         10,432.03  0xbbbb..ffcb               -> 0x06cf..f5ef               #25929298  0xc382dee9..8e2f
  $26.1m  WETH         10,432.03  0x06cf..f5ef               -> 0xbbbb..ffcb               #25929298  0xc382dee9..8e2f
  $25.0m  USDT        25,000,000  0x6c96..1dee               -> 0x359a..f806               #25929308  0x0d99a56f..e504
   $2.1m  USDT         2,054,455  0xb5e4..c24e               -> 0x71b8..7cdd               #25929289  0x59a3819f..a76e
   $2.1m  USDT         2,054,454  0xaa8b..3efb               -> 0xb5e4..c24e               #25929281  0xfe504bcf..3fc2
   $1.9m  USDC         1,869,344  0x92d4..13ee               -> 0xc3d6..cdc3               #25929304  0x79056413..ac22
   $1.6m  DAI          1,554,781  0x0 (mint or burn)         -> 0xa188..f98c               #25929319  0x2f3510d1..cdc0
   $1.6m  DAI          1,554,781  0xa188..f98c               -> 0xf6e7..3042               #25929319  0x2f3510d1..cdc0
   $1.6m  USDC         1,554,781  0x3730..7341               -> 0xa09f..d774               #25929319  0x2f3510d1..cdc0
   $1.5m  USDC         1,502,836  0x0580..425f               -> 0xee7a..4055               #25929283  0xc2cc1b34..220f
   $1.5m  USDT         1,500,000  0x549d..3425               -> 0x61f1..73b0               #25929303  0xb8b6fa43..7d70
   $1.5m  USDC         1,489,196  0x9322..2bd5               -> 0x06fd..e3b0               #25929304  0x60ebd251..fd2f
   $1.2m  USDC         1,176,000  0xc328..e239               -> 0x7388..38cf               #25929300  0x77942923..7542
   $1.1m  USDT         1,061,000  0x2387..086a               -> 0xcf0a..cd69               #25929328  0x68b11448..2895
14 transfers in blocks 25,929,279-25,929,328 (50 blocks, ~10 min): $94.5m total (WETH $52.1m, USDT $31.7m, USDC $7.6m, DAI $3.1m)
```

the two weth lines at the top are one transaction: 10k weth out and back in the same
block, which is what a flash loan looks like from here. since 0.2 that pair is folded into
one line tagged `[round trip]`, transfers from 0x0 are tagged `[mint]` and transfers to 0x0
or 0xdead `[burn]`; `--raw` prints every leg like above. a transfer is not a trade; the
labels and the etherscan link tell the rest.

## install

```
pipx install git+https://github.com/alinaschanz/bigmoves
pipx install "bigmoves[ens] @ git+https://github.com/alinaschanz/bigmoves"   # with --ens support
```

or clone it and run `python -m bigmoves` from the folder. python 3.10 or newer, no dependencies.

## use

```
bigmoves                                  # last 50 blocks, at least $1m, usdt usdc dai weth wbtc
bigmoves --blocks 300 --min-usd 5000000   # last hour, $5m and up
bigmoves --since 90m                      # a time window instead of a block count (a few header lookups)
bigmoves --tokens USDT,USDC --follow      # keep watching, new blocks every 12 s
bigmoves --eth                            # plain eth transfers too (full blocks, slower)
bigmoves --links                          # etherscan links instead of short hashes
bigmoves --json | jq .                    # json lines
bigmoves --labels mine.json               # your own {address: label} on top of the built-in list
bigmoves --raw                            # every transfer leg on its own line, no folding, no tags
bigmoves --ens                            # name the rest with ens reverse records (needs enslookup)
```

tokens on offer: USDT, USDC, DAI, WETH, stETH, WBTC, LINK, UNI. the live test checks every
address against `symbol()` and `decimals()` on chain, so the table cannot quietly rot.

## exit codes and scripting

`0` when the scan ran (even when nothing was above the threshold), `2` when no rpc answered or a
flag was wrong. `--json` prints one object per transfer with the raw addresses next to the labels, so
`bigmoves --json | jq -r 'select(.usd > 5e6) | .etherscan'` is the whole alerting pipeline.
in `--follow` mode every new batch is preceded by a `-- hh:mm:ss utc, blocks a-b` line on stdout.

## the labels

`bigmoves/labels.json`: about 290 addresses. exchanges (binance, coinbase, kraken, okx,
bitfinex, bybit, gemini, kucoin, gate.io, crypto.com, huobi, bitstamp, upbit, bithumb,
deribit ...), bridges (arbitrum, optimism, base, polygon, zksync), routers (uniswap, 1inch,
0x), treasuries (tether, circle, paxos), the beacon deposit contract, the ethereum
foundation. seeded from the public
[etherscan-labels](https://github.com/brianleect/etherscan-labels) dataset (a 2023 snapshot)
with newer entries added by hand from block explorers. an unlabeled address is printed
short (`0x1234..abcd`); pull requests with sourced labels are welcome.

## how it works

- `eth_getLogs` with the token addresses and the `Transfer` topic, 25 blocks per call
  (`--chunk`; public nodes cap the range or the result count, and the client moves to the
  next endpoint when one refuses).
- amounts come out of the log data and the token decimals; usd is amount x price, where
  stablecoins are a dollar by definition and weth, wbtc and friends are priced once per run
  from [coingecko](https://www.coingecko.com/en/api). with `--no-price` only stablecoins are counted.
- `--eth` fetches full blocks (`eth_getBlockByNumber`) and keeps transactions whose value
  clears the threshold. that is the expensive path, so it is opt-in.
- endpoints: publicnode, drpc, mevblocker, tenderly, blastapi, in that order, or `--rpc` yours.

## see also

- [ens-lookup](https://github.com/alinaschanz/ens-lookup): the names behind the addresses
- [stablepeg](https://github.com/alinaschanz/stablepeg): whether the stablecoins moving here are still a dollar
- [gasweek](https://github.com/alinaschanz/gasweek), [onchain-notes](https://github.com/alinaschanz/onchain-notes)
- the notes: [alinaschanz.life](https://alinaschanz.life), the short version on [x](https://x.com/alinaschanz)

## verify a release

from the next release on, every release carries the sdist and the wheel, a `SHA256SUMS` file, an
opentimestamps proof of that file, and a build provenance attestation made in github's own signing
flow. with the files downloaded into one folder:

    sha256sum -c SHA256SUMS
    gh attestation verify ./*.whl --owner alinaschanz
    ots verify SHA256SUMS.ots

the attestation names the commit and the workflow run that produced the file; the timestamp proves
the checksums existed before a certain bitcoin block; the commit itself is
[signed](https://alinaschanz.life/verify/#commits).

## license

[mit](LICENSE). the label list is data collected from public block explorers; check before
you rely on it.
