from typing import Any
from html import escape


def html_safe(value: Any) -> str:
    return escape("" if value is None else str(value))



