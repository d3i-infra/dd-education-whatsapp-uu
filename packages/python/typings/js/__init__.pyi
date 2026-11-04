"""Type stub for the Pyodide js module.

This module only exists at runtime in the Pyodide WebAssembly environment.
It provides access to JavaScript objects from Python.
"""
from typing import Any

def __getattr__(name: str) -> Any: ...
