# PromptSpec textX DSL

PromptSpec is a small external DSL for structured prompt engineering. It uses **textX** to define a grammar, parse `.promptx` files, validate simple well-formedness rules, and generate ready-to-use prompt text files.

## Project idea

Plain prompts often mix several concerns in one text block: role, task, inputs, constraints, examples, and expected output format. PromptSpec makes these prompt parts explicit in a small DSL.

Example DSL input:

```text
prompt ResearchSummary {
    role "You are a helpful research assistant."
    task "Summarize {{title}} using {{abstract}}."
    input title : "Title of the paper"
    input abstract : "Abstract of the paper"
    constraint "Use clear bullet points."
    constraint "Do not invent details."
    output markdown
}
```

The tool parses this structured specification and generates a final prompt text file.

## Files

```text
promptspec-textx/
├── README.md
├── grammar.tx
├── promptspec.py
├── requirements.txt
└── examples/
    └── research_summary.promptx
```

## Setup on macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Run the project

Check that the DSL file is valid:

```bash
python3 promptspec.py examples/research_summary.promptx --check
```

Generate a `.txt` prompt file:

```bash
python3 promptspec.py examples/research_summary.promptx --out outputs
```

Show the generated prompt:

```bash
cat outputs/ResearchSummary.txt
```

Generate with runtime values:

```bash
python3 promptspec.py examples/research_summary.promptx \
  --set title="Text2VQL" \
  --set abstract="A framework for generating VQL queries from natural language."
```

Read a new DSL specification from the terminal at runtime:

```bash
cat <<'PROMPTSPEC' | python3 promptspec.py --stdin --set topic="domain-specific languages"
prompt RuntimeDemo {
    role "You explain technical topics to students."
    task "Explain {{topic}} in simple words."
    input topic : "Topic to explain"
    constraint "Use no more than five bullet points."
    output markdown
}
PROMPTSPEC
```

## What this demonstrates

This project demonstrates a small DSL implementation pipeline:

1. **Concrete syntax:** `.promptx` files written by the user.
2. **Language definition:** `grammar.tx` defines the valid structure.
3. **Parsing and model creation:** textX parses the DSL into Python model objects.
4. **Static validation:** `promptspec.py` checks duplicate prompt names, duplicate input names, and undeclared placeholders.
5. **Generation:** the parsed model is translated into ready-to-use prompt text.
