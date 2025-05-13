from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from typing import Dict, Any


class CurrencyQAAgent:
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initializes the LangChain-powered Cypher QA agent."""
        self.prompt_template = PromptTemplate(
            input_variables=["question"],
            template="""
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
        )

        self.llm = AzureChatOpenAI(
            openai_api_key=config["azure_openai"]["api_key"],
            openai_api_version=config["azure_openai"]["api_version"],
            azure_endpoint=config["azure_openai"]["endpoint"],
            deployment_name=config["azure_openai"]["deployment_name"],
            temperature=0
        )

        self.graph = Neo4jGraph(
            url=config["neo4j"]["uri"],
            username=config["neo4j"]["user"],
            password=config["neo4j"]["password"]
        )

        self.chain = GraphCypherQAChain.from_llm(
            graph=self.graph,
            llm=self.llm,
            cypher_prompt=self.prompt_template,
            verbose=True,
            allow_dangerous_requests=True
        )

    def ask(self, question: str) -> str:
        """Runs the agent with a given question."""
        return self.chain.invoke(question)
