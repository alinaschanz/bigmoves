"""the tokens worth watching, with the decimals they use and how to price them."""
from __future__ import annotations

from dataclasses import dataclass

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # keccak256("Transfer(address,address,uint256)")


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str
    decimals: int
    coingecko: str | None = None  # coingecko id for the price; None means "it is a dollar"

    @property
    def stable(self) -> bool:
        return self.coingecko is None


TOKENS: dict[str, Token] = {
    t.symbol: t
    for t in (
        Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
        Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
        Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18),
        Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18, "ethereum"),
        Token("stETH", "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", 18, "ethereum"),
        Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8, "bitcoin"),
        Token("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA", 18, "chainlink"),
        Token("UNI", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", 18, "uniswap"),
    )
}
DEFAULT_SYMBOLS = ("USDT", "USDC", "DAI", "WETH", "WBTC")
ETH = Token("ETH", "0x" + "0" * 40, 18, "ethereum")


def by_address(tokens: list[Token]) -> dict[str, Token]:
    return {t.address.lower(): t for t in tokens}


def pick(symbols: str | None) -> list[Token]:
    """comma separated symbols -> tokens; unknown symbols raise KeyError."""
    wanted = [s.strip() for s in (symbols or ",".join(DEFAULT_SYMBOLS)).split(",") if s.strip()]
    lookup = {k.lower(): v for k, v in TOKENS.items()}
    out = []
    for s in wanted:
        if s.lower() not in lookup:
            raise KeyError(s)
        out.append(lookup[s.lower()])
    return out
