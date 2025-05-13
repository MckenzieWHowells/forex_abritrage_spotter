from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from neo4j import GraphDatabase, Transaction
import requests
import toml
from typing import List, Dict, Any


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


# === Main Execution ===
if __name__ == "__main__":
    config: Dict[str, Any] = toml.load("config.toml")
    currencies = get_currency_list()
    if not currencies:
        print("No currencies fetched. Exiting.")
        exit(1)

    node_query = load_cypher_query("code/cypher/create_currency.cypher")
    edge_query = load_cypher_query("code/cypher/create_exchange_rate.cypher")
    if not node_query or not edge_query:
        print("Failed to load Cypher queries. Exiting.")
        exit(1)

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

    graph.close()

    # === LangChain Agent Query ===
    FEW_SHOT_PROMPT = """
    # Please ALWAYS assign the exchange relationship to a variable (e.g., [r:EXCHANGE_TO])
    # so that you can access properties like r.rate in the RETURN clause.

    # Examples
    # Question: What is the exchange rate from USD to other currencies?
    MATCH (c1:Currency {{code: 'USD'}})-[r:EXCHANGE_TO]->(c2:Currency)
    RETURN c2.code, r.rate

    # Question: Which currencies have the highest exchange rate from EUR?
    MATCH (c1:Currency {{code: 'EUR'}})-[r:EXCHANGE_TO]->(c2:Currency)
    RETURN c2.code, c2.description, r.rate
    ORDER BY r.rate DESC

    # Now answer this question:
    Question: {question}
    """

    cypher_prompt = PromptTemplate(
        input_variables=["question"],
        template=FEW_SHOT_PROMPT
    )

    llm = AzureChatOpenAI(
        openai_api_key=config["azure_openai"]["api_key"],
        openai_api_version=config["azure_openai"]["api_version"],
        azure_endpoint=config["azure_openai"]["endpoint"],
        deployment_name=config["azure_openai"]["deployment_name"],
        temperature=0
    )

    neo4j_langchain_graph = Neo4jGraph(
        url=config["neo4j"]["uri"],
        username=config["neo4j"]["user"],
        password=config["neo4j"]["password"]
    )

    chain = GraphCypherQAChain.from_llm(
        graph=neo4j_langchain_graph,
        llm=llm,
        cypher_prompt=cypher_prompt,
        verbose=True,
        allow_dangerous_requests=True
    )

    # Sample query to test
    response = chain.invoke("Which currencies have the lowest exchange rate from EUR?")
    print("Answer:", response)
