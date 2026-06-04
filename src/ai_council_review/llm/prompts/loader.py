"""Prompt loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2


def load_prompt(name: str, **variables: Any) -> str:
    """Load a prompt template from the prompts directory.

    Args:
        name: Prompt name (e.g., "generalist"). The file `prompts/{name}.txt`
            will be loaded.
        **variables: Jinja2 template variables for substitution.

    Returns:
        The rendered prompt text.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompts_dir = Path(__file__).parent
    prompt_file = prompts_dir / f"{name}.txt"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    template_text = prompt_file.read_text(encoding="utf-8")
    template = jinja2.Template(template_text)
    return template.render(**variables)
