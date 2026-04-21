from rich.prompt import Confirm, Prompt
from rich import print as rprint


def confirm(prompt: str) -> bool:
    return Confirm.ask(prompt)


def confirm_str(prompt: str) -> str:
    return "yes" if Confirm.ask(prompt) else "no"


def ask_choices(prompt: str, choices: list[str]) -> str:
    for i, choice in enumerate(choices):
        rprint(f" [{i+1}] {choice}")
    choice = Prompt.ask(prompt, choices=[ str(i+1) for i in range(len(choices)) ])
    return choices[int(choice)-1]
