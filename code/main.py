"""
Currency Graph Builder

This script:
1. Fetches currency codes and exchange rates using the Frankfurter API.
2. Loads Cypher queries from file.
3. Connects to a Neo4j database.
4. Creates currency nodes and exchange rate relationships in the graph.

Author: Your Name
"""

from neo4j import GraphDatabase, Transaction
import requests
import toml
from typing import List, Dict, Any


def get_currency_list() -> List[Dict[str, str]]:
    """
    Fetch a list of available currencies and their descriptions from the Frankfurter API.

    Returns:
        A list of dictionaries, each with 'code' and 'description' keys.
    """
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
    """
    Get current exchange rates for a given base currency from the Frankfurter API.

    Args:
        base_currency: Currency code to use as the base (default is 'EUR').

    Returns:
        A dictionary containing the date, base currency, and a rates dictionary.
    """
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
    """
    Load a Cypher query from a text file.

    Args:
        filepath: Path to the Cypher query file.

    Returns:
        The Cypher query as a string.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Cypher query file '{filepath}' not found.")
        return ""
    except Exception as e:
        print(f"Error reading Cypher query file: {e}")
        return ""


class CurrencyGraph:
    """
    A class to manage creation of currency nodes and exchange rate relationships in Neo4j.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        """
        Initialize the CurrencyGraph instance and connect to Neo4j.

        Args:
            uri: Bolt URI of the Neo4j instance.
            user: Neo4j username.
            password: Neo4j password.
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def create_currency_nodes(self, currencies: List[Dict[str, str]], cypher_query: str) -> None:
        """
        Create currency nodes in the graph using a Cypher query.

        Args:
            currencies: List of currency dictionaries with 'code' and 'description'.
            cypher_query: Cypher query for creating nodes.
        """
        if not cypher_query:
            print("Cypher query is empty. Aborting node creation.")
            return

        with self.driver.session() as session:
            for currency in currencies:
                session.execute_write(self._create_node, currency, cypher_query)

    def create_exchange_relationships(self, rates_data: Dict[str, Any], cypher_query: str) -> None:
        """
        Create exchange rate relationships from the given rates data.

        Args:
            rates_data: Dictionary with 'base', 'rates', and 'date'.
            cypher_query: Cypher query for creating relationships.
        """
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
        """
        Transaction to create a single currency node.

        Args:
            tx: Active Neo4j transaction.
            currency: Dictionary with 'code' and 'description'.
            query: Cypher query for node creation.
        """
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
        """
        Transaction to create an exchange rate relationship.

        Args:
            tx: Active Neo4j transaction.
            from_code: Source currency code.
            to_code: Target currency code.
            rate: Exchange rate.
            date: Date of the rate.
            query: Cypher query for relationship creation.
        """
        tx.run(query, from_code=from_code, to_code=to_code, rate=rate, date=date)


# === 5. Main Execution ===
if __name__ == "__main__":
    currencies = get_currency_list()
    if not currencies:
        print("No currencies fetched. Exiting.")
        exit(1)

    node_query = load_cypher_query("code/cypher/create_currency.cypher")
    edge_query = load_cypher_query("code/cypher/create_exchange_rate.cypher")
    if not node_query or not edge_query:
        print("Failed to load Cypher queries. Exiting.")
        exit(1)

    try:
        config: Dict[str, Any] = toml.load("config.toml")
        uri: str = config["neo4j"]["uri"]
        user: str = config["neo4j"]["user"]
        password: str = config["neo4j"]["password"]
        graph = CurrencyGraph(uri, user, password)

        graph.create_currency_nodes(currencies, node_query)
        print(f"Added {len(currencies)} currency nodes to Neo4j.")

        rates_dict: Dict[str, Dict[str, Any]] = {}
        for currency in [c["code"] for c in currencies]:
            rates = get_exchange_rates(currency)
            if rates:
                rates_dict[currency] = rates

        for base_currency, rates in rates_dict.items():
            graph.create_exchange_relationships(rates, edge_query)
            print(f"Added exchange rate relationships from {base_currency}.")

    except Exception as e:
        print(f"Error interacting with Neo4j: {e}")
    finally:
        graph.close()
