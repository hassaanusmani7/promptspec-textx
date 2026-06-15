#!/usr/bin/env python3
"""PromptSpec: a small textX-based DSL implementation.

This script implements the complete language-processing pipeline:
1. load the textX grammar,
2. parse a .promptx file or DSL text from standard input,
3. validate simple well-formedness rules,
4. generate ready-to-use prompt text.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, List

from textx import metamodel_from_file


ROOT_DIR = Path(__file__).resolve().parent
GRAMMAR_FILE = ROOT_DIR / "grammar.tx"
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class PromptSpecError(Exception):
    """Raised when the DSL text is syntactically valid but not well-formed."""


def parse_assignments(values: Iterable[str]) -> Dict[str, str]:
    """Parse command-line values of the form name=value."""
    result: Dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise PromptSpecError(f"Runtime value must use name=value syntax: {item}")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise PromptSpecError(f"Runtime value has an empty name: {item}")
        result[name] = value
    return result


def load_metamodel():
    """Create the textX metamodel from the grammar file."""
    return metamodel_from_file(str(GRAMMAR_FILE), autokwd=True)


def load_model(path: Path | None, from_stdin: bool):
    """Parse either a .promptx file or DSL text from standard input."""
    metamodel = load_metamodel()
    if from_stdin:
        text = ""
        try:
            while True:
                text += input() + "\n"
        except EOFError:
            pass
        return metamodel.model_from_str(text, file_name="<stdin>")

    if path is None:
        raise PromptSpecError("Please provide a .promptx file, or use --stdin.")
    return metamodel.model_from_file(str(path))


def find_placeholders(text: str) -> List[str]:
    """Return placeholder names used in a text fragment.

    Placeholders follow the form {{name}}.
    """
    return PLACEHOLDER_PATTERN.findall(text or "")


def validate_prompt(prompt) -> List[str]:
    """Check well-formedness rules for one prompt specification."""
    issues: List[str] = []

    input_names = [item.name for item in prompt.inputs]
    declared_inputs = set(input_names)

    # Rule 1: input declarations must be unique.
    seen_inputs = set()
    for name in input_names:
        if name in seen_inputs:
            issues.append(f"Prompt '{prompt.name}' declares input '{name}' more than once.")
        seen_inputs.add(name)

    # Rule 2: placeholders used in prompt text must be declared as inputs.
    used_placeholders = set()
    text_fragments = [prompt.role.text, prompt.task.text]
    text_fragments.extend(constraint.text for constraint in prompt.constraints)
    for example in prompt.examples:
        text_fragments.append(example.user.text)
        text_fragments.append(example.assistant.text)

    for fragment in text_fragments:
        used_placeholders.update(find_placeholders(fragment))

    undeclared = sorted(used_placeholders - declared_inputs)
    for name in undeclared:
        issues.append(
            f"Prompt '{prompt.name}' uses placeholder '{{{{{name}}}}}' "
            "but no matching input is declared."
        )

    return issues


def validate_model(model) -> None:
    """Validate all prompts in the parsed model."""
    issues: List[str] = []
    prompt_names = [prompt.name for prompt in model.prompts]

    # Rule 3: prompt names should be unique inside one file.
    seen_prompts = set()
    for name in prompt_names:
        if name in seen_prompts:
            issues.append(f"Prompt name '{name}' is used more than once.")
        seen_prompts.add(name)

    for prompt in model.prompts:
        issues.extend(validate_prompt(prompt))

    if issues:
        raise PromptSpecError("\n".join(issues))


def fill_placeholders(text: str, values: Dict[str, str]) -> str:
    """Replace {{name}} placeholders with runtime values when provided.

    If a value is not provided, the placeholder is kept in the generated prompt.
    This supports both reusable prompt templates and runtime prompt generation.
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return values.get(name, match.group(0))

    return PLACEHOLDER_PATTERN.sub(replace, text or "")


def render_prompt(prompt, values: Dict[str, str]) -> str:
    """Generate a ready-to-use prompt from one PromptSpec model object."""
    lines: List[str] = []

    lines.extend(["Role", "----", fill_placeholders(prompt.role.text, values), ""])
    lines.extend(["Task", "----", fill_placeholders(prompt.task.text, values), ""])

    if prompt.inputs:
        lines.extend(["Inputs", "------"])
        for item in prompt.inputs:
            placeholder = "{{" + item.name + "}}"
            shown_value = values.get(item.name, placeholder)
            if item.description:
                lines.append(f"- {item.name}: {shown_value} - {item.description}")
            else:
                lines.append(f"- {item.name}: {shown_value}")
        lines.append("")

    if prompt.constraints:
        lines.extend(["Constraints", "-----------"])
        for constraint in prompt.constraints:
            lines.append(f"- {fill_placeholders(constraint.text, values)}")
        lines.append("")

    if prompt.examples:
        lines.extend(["Examples", "--------"])
        for example in prompt.examples:
            lines.append(f"Example: {example.name}")
            lines.append(f"User: {fill_placeholders(example.user.text, values)}")
            lines.append(f"Assistant: {fill_placeholders(example.assistant.text, values)}")
            lines.append("")

    lines.extend(["Expected output format", "----------------------", prompt.output.format])
    return "\n".join(lines).strip() + "\n"


def output_filename(prompt_name: str) -> str:
    """Create a text filename from the prompt name."""
    return f"{prompt_name}.txt"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse, validate, and generate prompt text from a PromptSpec DSL file."
    )
    parser.add_argument("file", nargs="?", help="Path to a .promptx DSL file")
    parser.add_argument("--stdin", action="store_true", help="Read DSL text from standard input")
    parser.add_argument("--check", action="store_true", help="Only parse and validate the DSL input")
    parser.add_argument("--out", help="Directory for generated .txt prompt files")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Runtime value for a declared input placeholder. Can be used multiple times.",
    )
    args = parser.parse_args()

    try:
        values = parse_assignments(args.set)
        model = load_model(Path(args.file) if args.file else None, args.stdin)
        validate_model(model)

        if args.check:
            target = args.file if args.file else "<stdin>"
            print(f"OK: {target}")
            return 0

        if args.out:
            output_dir = Path(args.out)
            output_dir.mkdir(parents=True, exist_ok=True)
            for prompt in model.prompts:
                target = output_dir / output_filename(prompt.name)
                target.write_text(render_prompt(prompt, values), encoding="utf-8")
                print(f"Generated {target}")
            return 0

        for index, prompt in enumerate(model.prompts):
            if index > 0:
                print("\n" + "=" * 60 + "\n")
            print(render_prompt(prompt, values))
        return 0

    except PromptSpecError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
