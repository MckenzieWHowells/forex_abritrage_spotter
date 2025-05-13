import toml
from currency_graph import CurrencyGraph, get_currency_list, get_exchange_rates, load_cypher_query
from typing import Dict, Any

def main():
    config: Dict[str, Any] = toml.load("config.toml")
    uri: str = config["neo4j"]["uri"]
    user: str = config["neo4j"]["user"]
    password: str = config["neo4j"]["password"]

    node_query = load_cypher_query("code/cypher/create_currency.cypher")
    edge_query = load_cypher_query("code/cypher/create_exchange_rate.cypher")
    if not node_query or not edge_query:
        print("Failed to load Cypher queries. Exiting.")
        exit(1)

    currencies = get_currency_list()
    if not currencies:
        print("No currencies fetched. Exiting.")
        exit(1)

    graph = CurrencyGraph(uri, user, password)
    graph.create_currency_nodes(currencies, node_query)
    print(f"Added {len(currencies)} currency nodes to Neo4j.")

    for currency in [c["code"] for c in currencies]:
        rates = get_exchange_rates(currency)
        if rates:
            graph.create_exchange_relationships(rates, edge_query)
            print(f"Added exchange rate relationships from {currency}.")

    graph.close()

if __name__ == "__main__":
    main()
