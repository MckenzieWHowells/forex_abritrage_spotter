from neo4j import GraphDatabase, Transaction
import requests
from typing import List, Dict, Any


class CurrencyGraph:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def create_currency_nodes(self, currencies: List[Dict[str, str]], cypher_query: str) -> None:
        if not cypher_query:
            print("Cypher query is empty. Aborting node creation.")
            return

        with self.driver.session() as session:
            for currency in currencies:
                session.execute_write(self._create_node, currency, cypher_query)

    def create_exchange_relationships(self, rates_data: Dict[str, Any], cypher_query: str) -> None:
        if not cypher_query or not rates_data:
            print("No data or query provided. Skipping relationship creation.")
            return

        with self.driver.session() as session:
            for to_code, rate in rates_data["rates"].items():
                session.execute_write(
                    self._create_relationship,
                    from_code=rates_data["base"],
                    to_code=to_code,
                    rate=rate,
                    date=rates_data["date"],
                    query=cypher_query
                )

    @staticmethod
    def _create_node(tx: Transaction, currency: Dict[str, str], query: str) -> None:
        tx.run(query, code=currency["code"], description=currency["description"])

    @staticmethod
    def _create_relationship(
        tx: Transaction,
        from_code: str,
        to_code: str,
        rate: float,
        date: str,
        query: str
    ) -> None:
        tx.run(query, from_code=from_code, to_code=to_code, rate=rate, date=date)


def get_currency_list() -> List[Dict[str, str]]:
    url = "https://api.frankfurter.app/currencies"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return [{"code": code, "description": name} for code, name in data.items()]
    except requests.RequestException as e:
        print(f"Error fetching currency list: {e}")
        return []


def get_exchange_rates(base_currency: str = "EUR") -> Dict[str, Any]:
    url = f"https://api.frankfurter.app/latest?from={base_currency}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return {
            "date": data["date"],
            "base": base_currency,
            "rates": data["rates"]
        }
    except requests.RequestException as e:
        print(f"Error fetching exchange rates: {e}")
        return {}


def load_cypher_query(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Cypher query file '{filepath}' not found.")
        return ""
    except Exception as e:
        print(f"Error reading Cypher query file: {e}")
        return ""
