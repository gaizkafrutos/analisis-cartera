"""Reading and validating the user's portfolio (CSV text or form rows). Pure: no files, no network.

Entry points:
    - `portfolio_from_csv(data, universe)`: CSV bytes/text -> PortfolioInputResult
    - `build_portfolio(raw_positions, universe)`: form rows -> PortfolioInputResult
"""

from radiografia.input.builder import build_portfolio, portfolio_from_csv

__all__ = ["build_portfolio", "portfolio_from_csv"]
