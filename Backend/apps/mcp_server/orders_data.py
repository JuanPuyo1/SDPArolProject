"""Stand-in CSV-backed sample data for the Orders/Business tools.

Not tenant-scoped by content — callers already validated the requester owns a
real machine via scoping.get_owned_machine() before reading from here. This
module just supplies representative example rows (multiple quote revisions,
etc.) until the quoting/ERP/contracts systems are connected.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[3] / 'Data' / 'Relational'


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list[dict], coercing pandas NaN to None (Pydantic-friendly).

    DataFrame.where(cond, None) doesn't reliably substitute None into
    pandas's native `str` dtype columns, so NaN is replaced per-value instead.
    """
    return [
        {key: (None if pd.isna(value) else value) for key, value in row.items()}
        for row in df.to_dict(orient='records')
    ]


class OrdersDataStore:
    def __init__(self, data_dir: Path = DATA_DIR):
        quotes_path = data_dir / 'quotes.csv'
        orders_path = data_dir / 'orders.csv'
        contracts_path = data_dir / 'contracts.csv'

        self.quotes = (
            pd.read_csv(quotes_path)
            if quotes_path.exists()
            else pd.DataFrame(columns=['quote_id', 'revision_number', 'quote_date', 'status', 'item_summary', 'amount_eur'])
        )
        self.orders = (
            pd.read_csv(orders_path)
            if orders_path.exists()
            else pd.DataFrame(columns=['order_id', 'quote_id', 'order_date', 'status', 'item_summary', 'amount_eur'])
        )
        self.contracts = (
            pd.read_csv(contracts_path)
            if contracts_path.exists()
            else pd.DataFrame(columns=['contract_id', 'type', 'start_date', 'end_date'])
        )

    def quote_history(self, quote_id: str | None = None) -> list[dict]:
        df = self.quotes
        if quote_id:
            df = df[df.quote_id == quote_id]
        df = df.sort_values(['quote_id', 'revision_number'])
        return _records(df)

    def order_status(self) -> list[dict]:
        return _records(self.orders)

    def contract_info(self) -> list[dict]:
        return _records(self.contracts)


@lru_cache(maxsize=1)
def get_store() -> OrdersDataStore:
    return OrdersDataStore()
