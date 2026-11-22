"""try_agent.py - run from the project root:  python try_agent.py"""
from src.ai.gemini_agent import ask

QUESTIONS = [
    "Which mapped features are within 50 km of Sudbury?",
    "Find Ontario mine features associated with nickel and summarize the Ontario "
    "nickel quantity produced over the last 3 years.",
]

for q in QUESTIONS:
    out = ask(q)
    print("\nQ:", q)
    print("A:", out["answer"])
    print("TOOLS:", out["tool_calls"])
