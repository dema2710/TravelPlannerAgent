"""Currency helpers for the simulated travel data.

All mock prices are authored in EUR and converted with a fixed, simulated rate
table. These rates are illustrative only; they are not live financial data.
"""

from __future__ import annotations

from typing import Final

# Simulated fixed rates: one EUR equals this many units of the target currency.
EXCHANGE_RATES_FROM_EUR: Final[dict[str, float]] = {
    "EUR": 1.0,
    "USD": 1.08,
    "GBP": 0.86,
    "CZK": 24.50,
    "CHF": 0.95,
}

SUPPORTED_CURRENCIES: Final[tuple[str, ...]] = tuple(sorted(EXCHANGE_RATES_FROM_EUR))


class CurrencyError(ValueError):
    """Raised when a currency is unknown or an amount cannot be converted."""


def normalize_currency(currency: str) -> str:
    """Return a validated three-letter uppercase currency code."""
    normalized = currency.strip().upper()
    if normalized not in EXCHANGE_RATES_FROM_EUR:
        supported = ", ".join(SUPPORTED_CURRENCIES)
        raise CurrencyError(
            f"Unsupported currency '{currency}'. Supported simulated currencies: {supported}."
        )
    return normalized


def round_money(value: float) -> float:
    """Round a monetary amount to two decimal places."""
    return round(float(value) + 1e-9, 2)


def convert_from_eur(amount_eur: float, currency: str) -> float:
    """Convert an EUR amount using the fixed simulated exchange rate."""
    code = normalize_currency(currency)
    if amount_eur < 0:
        raise CurrencyError("Monetary amounts cannot be negative.")
    return round_money(amount_eur * EXCHANGE_RATES_FROM_EUR[code])


def format_money(amount: float, currency: str) -> str:
    """Format a monetary value for human-readable CLI output."""
    return f"{round_money(amount):,.2f} {currency.upper()}"
