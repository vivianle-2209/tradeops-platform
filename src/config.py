"""Small, explicit configuration boundary. Importing this module performs no I/O."""
from dataclasses import dataclass
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SLA_MINUTES = {"CRITICAL": 15, "HIGH": 30, "MEDIUM": 60, "LOW": 240}
SLA_AT_RISK_FRACTION = 0.75
ESCALATION_SEVERITIES = frozenset({"HIGH", "CRITICAL"})
PRICE_TOLERANCE = 0.01
LATE_CLEARING_SECONDS = 15 * 60


@dataclass(frozen=True)
class Settings:
    db_path: Path = PROJECT_ROOT / "data/tradeops.duckdb"
    symbols: tuple[str, ...] = ("MSFT", "AAPL", "NVDA", "AMZN", "META", "GOOGL", "TSLA")
    source: str = "ALPACA_IEX"
    initial_lookback_minutes: int = 30
    overlap_minutes: int = 2
    page_limit: int = 1000
    request_timeout: int = 30
    max_window_hours: int = 24
    retry_base_seconds: int = 60
    retry_max_seconds: int = 3600
    dispatch_batch_size: int = 100
    api_key: str = ""
    secret_key: str = ""
    webhook_url: str = ""

    def __post_init__(self):
        if not self.symbols or any(not s.strip() for s in self.symbols):
            raise ValueError("At least one nonempty symbol is required")
        if self.overlap_minutes < 0 or self.initial_lookback_minutes <= 0:
            raise ValueError("Lookback must be positive and overlap nonnegative")
        if self.overlap_minutes >= self.max_window_hours * 60:
            raise ValueError("Overlap must be shorter than the maximum fetch window")
        if min(self.page_limit, self.request_timeout, self.max_window_hours,
               self.retry_base_seconds, self.retry_max_seconds, self.dispatch_batch_size) <= 0:
            raise ValueError("API limits and retry settings must be positive")

    @classmethod
    def from_env(cls):
        return cls(
            db_path=Path(os.getenv("TRADEOPS_DB_PATH", str(cls.db_path))),
            symbols=tuple(s.strip().upper() for s in os.getenv(
                "TRADEOPS_SYMBOLS", ",".join(cls.symbols)).split(",") if s.strip()),
            initial_lookback_minutes=int(os.getenv("TRADEOPS_LOOKBACK_MINUTES", "30")),
            overlap_minutes=int(os.getenv("TRADEOPS_OVERLAP_MINUTES", "2")),
            page_limit=int(os.getenv("TRADEOPS_PAGE_LIMIT", "1000")),
            max_window_hours=int(os.getenv("TRADEOPS_MAX_WINDOW_HOURS", "24")),
            retry_base_seconds=int(os.getenv("TRADEOPS_RETRY_SECONDS", "60")),
            retry_max_seconds=int(os.getenv("TRADEOPS_RETRY_MAX_SECONDS", "3600")),
            dispatch_batch_size=int(os.getenv("TRADEOPS_DISPATCH_BATCH_SIZE", "100")),
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            webhook_url=os.getenv("N8N_WEBHOOK_URL", ""),
        )
