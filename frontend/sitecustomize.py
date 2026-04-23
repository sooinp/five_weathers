"""
Startup compatibility patch for local frontend runs.

This is imported automatically by Python during startup when running from the
frontend directory, before `solara.__main__` imports `uvicorn.main`.
"""

from __future__ import annotations

from typing import get_args


def _patch_uvicorn_loop_choices() -> None:
    import click
    import uvicorn.main

    if hasattr(uvicorn.main, "LOOP_CHOICES"):
        return

    try:
        from uvicorn.config import LoopFactoryType

        choices = [value for value in get_args(LoopFactoryType) if value != "none"]
    except Exception:
        choices = ["auto", "asyncio", "uvloop"]

    uvicorn.main.LOOP_CHOICES = click.Choice(choices)


_patch_uvicorn_loop_choices()
