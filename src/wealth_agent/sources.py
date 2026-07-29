from __future__ import annotations

import csv
import io
import json
import re
import struct
from pathlib import Path
from typing import Protocol

from .models import Holding, Portfolio


class PortfolioSource(Protocol):
    def load(self, user_id: str) -> Portfolio: ...


def _history(value: object) -> list[float]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [float(item) for item in value]
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [item for item in text.split(";") if item.strip()]
    if not isinstance(parsed, list):
        raise ValueError("return_history must be a JSON array or semicolon-separated numbers")
    return [float(item) for item in parsed]


def _holding_from_row(row: dict[str, object]) -> Holding:
    return Holding(
        symbol=str(row["symbol"]),
        name=str(row.get("name") or row["symbol"]),
        asset_class=str(row["asset_class"]),
        quantity=float(row["quantity"]),
        price=float(row["price"]),
        cost_basis=float(row["cost_basis"]),
        annual_volatility=float(row["annual_volatility"]),
        expected_return=float(row["expected_return"]),
        return_history=_history(row.get("return_history")),
    )


class JsonPortfolioSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self, user_id: str = "demo") -> Portfolio:
        def reject_constant(value: str) -> None:
            raise ValueError(f"Invalid non-finite JSON number: {value}")

        payload = json.loads(self.path.read_text(encoding="utf-8"), parse_constant=reject_constant)
        if not isinstance(payload, dict) or not isinstance(payload.get("holdings"), list):
            raise ValueError("portfolio JSON must contain a holdings list")
        portfolio_user = str(payload.get("user_id", user_id)).strip()
        if portfolio_user != user_id:
            raise LookupError(f"No local portfolio found for {user_id}")
        try:
            holdings = [Holding(**item) for item in payload["holdings"]]
            horizon_years = payload.get("horizon_years", 10)
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"Invalid portfolio JSON: {exc}") from exc
        return Portfolio(portfolio_user, payload.get("risk_tolerance", "moderate"), horizon_years, holdings)


class OneLakePortfolioSource:
    """Reads a CSV from Microsoft Fabric OneLake through its ADLS-compatible endpoint."""

    def __init__(self, workspace: str, lakehouse: str, path: str = "Files/portfolio.csv") -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.filedatalake import DataLakeServiceClient

        if not workspace or not lakehouse:
            raise ValueError("FABRIC_WORKSPACE and FABRIC_LAKEHOUSE are required")
        service = DataLakeServiceClient("https://onelake.dfs.fabric.microsoft.com", credential=DefaultAzureCredential())
        self.client = service.get_file_system_client(workspace).get_file_client(f"{lakehouse}.Lakehouse/{path}")

    def load(self, user_id: str) -> Portfolio:
        content = self.client.download_file().readall().decode("utf-8")
        rows = [row for row in csv.DictReader(io.StringIO(content)) if row.get("user_id") == user_id]
        if not rows:
            raise LookupError(f"No Fabric holdings found for {user_id}")
        holdings = [_holding_from_row(row) for row in rows]
        return Portfolio(user_id, rows[0].get("risk_tolerance", "moderate"), int(rows[0].get("horizon_years", 10)), holdings)


class FabricSqlPortfolioSource:
    """Read-only adapter for a Fabric Warehouse or Lakehouse SQL analytics endpoint."""

    COLUMNS = "user_id,symbol,name,asset_class,quantity,price,cost_basis,annual_volatility,expected_return,risk_tolerance,horizon_years,return_history"

    def __init__(
        self,
        endpoint: str,
        database: str,
        table: str = "dbo.portfolio",
        connector=None,
        timeout: int = 15,
    ) -> None:
        if not endpoint.strip() or not database.strip() or any(character in endpoint + database for character in ";\n\r"):
            raise ValueError("Fabric SQL endpoint and database are required and cannot contain connection delimiters")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", table):
            raise ValueError("FABRIC_PORTFOLIO_TABLE must be table or schema.table")
        if not 1 <= timeout <= 120:
            raise ValueError("Fabric SQL timeout must be between 1 and 120 seconds")
        self.table, self.timeout = table, timeout
        if connector is not None:
            self.connector = connector
            return
        try:
            import pyodbc
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise RuntimeError("Install the Fabric SQL profile with `pip install -r requirements-fabric.txt`") from exc
        token = DefaultAzureCredential().get_token("https://database.windows.net/.default").token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token)}s", len(token), token)
        connection_string = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server={endpoint};Database={database};Encrypt=yes;TrustServerCertificate=no"
        )
        self.connector = lambda: pyodbc.connect(connection_string, attrs_before={1256: token_struct}, timeout=timeout)

    def load(self, user_id: str) -> Portfolio:
        if not user_id.strip() or len(user_id) > 100:
            raise ValueError("user_id must be between 1 and 100 characters")
        connection = self.connector()
        try:
            cursor = connection.cursor()
            cursor.execute(f"SELECT {self.COLUMNS} FROM {self.table} WHERE user_id = ?", user_id)
            names = [str(item[0]) for item in cursor.description]
            rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            connection.close()
        if not rows:
            raise LookupError(f"No Fabric SQL holdings found for {user_id}")
        holdings = [_holding_from_row(row) for row in rows]
        return Portfolio(user_id, str(rows[0].get("risk_tolerance") or "moderate"), int(rows[0].get("horizon_years") or 10), holdings)
