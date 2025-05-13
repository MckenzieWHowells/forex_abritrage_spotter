import toml
import sys
from code.agent.currency_agent import CurrencyQAAgent

def main():
    config = toml.load("config.toml")
    agent = CurrencyQAAgent(config)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Enter your question about currencies: ")

    response = agent.ask(question)
    print("\nAnswer:", response)

if __name__ == "__main__":
    main()