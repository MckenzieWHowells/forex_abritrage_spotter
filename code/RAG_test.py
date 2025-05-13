from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
import toml

# Load config
config = toml.load("config.toml")
azure = config["azure_openai"]

# Neo4j connection
graph = Neo4jGraph(
    url=config["neo4j"]["uri"],
    username=config["neo4j"]["user"],
    password=config["neo4j"]["password"]
)

# Few-shot prompt template
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

# Azure LLM setup
llm = AzureChatOpenAI(
    openai_api_key=azure["api_key"],
    openai_api_version=azure["api_version"],
    azure_endpoint=azure["endpoint"],
    deployment_name=azure["deployment_name"],
    temperature=0
)

chain = GraphCypherQAChain.from_llm(
    graph=graph,
    llm=llm,
    cypher_prompt=cypher_prompt,
    verbose=True,
    allow_dangerous_requests=True
)

# Run query
response = chain.invoke("Which currencies have the lowest exchange rate from EUR?")
print("Answer:", response)
