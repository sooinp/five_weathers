"""
Compatibility launcher for local Solara runs.

Solara 1.40 expects uvicorn.main.LOOP_CHOICES, which was removed in newer
uvicorn releases. This wrapper patches that symbol before delegating to
solara's CLI entrypoint.
"""

from __future__ import annotations

from typing import get_args


def _patch_uvicorn_for_solara() -> None:
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


def main() -> None:
    _patch_uvicorn_for_solara()

    try:
        import solara.__main__ as solara_main
    except ModuleNotFoundError as exc:
        if exc.name == "traitlets":
            raise SystemExit(
                "Missing dependency 'traitlets'. Run `pip install -r requirements.txt` "
                "inside the frontend directory, then start the frontend again."
            ) from exc
        raise

    solara_main.main()


if __name__ == "__main__":
    main()
