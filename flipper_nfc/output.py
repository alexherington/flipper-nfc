"""Human-friendly and machine-friendly CLI output."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.theme import Theme

THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "dim": "dim",
        "accent": "bold magenta",
    }
)


def parse_device_info(raw: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        info[key.strip()] = value.strip()
    return info


@dataclass
class CliOutput:
    """Route messages to Rich (human) or JSON (machine)."""

    json_mode: bool = False
    quiet: bool = False
    no_color: bool = False
    _consoles: tuple[Console, Console] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        color = not self.no_color and not os.environ.get("NO_COLOR")
        force = not self.quiet and not self.json_mode and sys.stderr.isatty()
        self._consoles = (
            Console(theme=THEME, stderr=False, no_color=not color, force_terminal=force),
            Console(theme=THEME, stderr=True, no_color=not color, force_terminal=force),
        )

    @property
    def stdout(self) -> Console:
        return self._consoles[0]

    @property
    def stderr(self) -> Console:
        return self._consoles[1]

    @classmethod
    def from_args(cls, args: Any) -> CliOutput:
        json_mode = bool(getattr(args, "json", False))
        quiet = bool(getattr(args, "quiet", False)) or json_mode
        no_color = bool(getattr(args, "no_color", False))
        if not sys.stdout.isatty() and not json_mode:
            quiet = True
        return cls(json_mode=json_mode, quiet=quiet, no_color=no_color)

    @property
    def interactive(self) -> bool:
        return (
            not self.json_mode
            and not self.quiet
            and sys.stdin.isatty()
            and sys.stderr.isatty()
        )

    def info(self, msg: str) -> None:
        if self.quiet:
            return
        self.stderr.print(f"[info]ℹ[/]  {msg}")

    def success(self, msg: str) -> None:
        if self.quiet:
            return
        self.stderr.print(f"[success]✅[/] {msg}")

    def warning(self, msg: str) -> None:
        if self.quiet:
            return
        self.stderr.print(f"[warning]⚠️[/]  {msg}")

    def error(self, msg: str) -> None:
        if self.json_mode:
            self.emit_error(msg)
            return
        self.stderr.print(f"[error]❌[/] {msg}")

    def emit(self, data: dict[str, Any]) -> None:
        """Print a JSON result to stdout."""
        print(json.dumps(data))

    def emit_error(self, msg: str, code: int = 1) -> None:
        """Print a JSON error to stderr and exit."""
        print(json.dumps({"ok": False, "error": msg}), file=sys.stderr)
        raise SystemExit(code)

    def fail(self, msg: str, code: int = 1) -> None:
        if self.json_mode:
            self.emit_error(msg, code=code)
        self.error(msg)
        raise SystemExit(code)

    def confirm(self, prompt: str, *, default: bool = True) -> bool:
        if not self.interactive:
            return False
        return Confirm.ask(prompt, default=default, console=self.stderr)

    @contextmanager
    def status(self, msg: str):
        if self.quiet:
            yield _NullStatus()
            return
        with self.stderr.status(msg, spinner="dots") as status:
            yield status

    def print_table(self, table: Table) -> None:
        if self.quiet and not self.json_mode:
            return
        self.stdout.print(table)

    def print_text(self, text: str) -> None:
        if self.json_mode:
            return
        self.stdout.print(text)


class _NullStatus:
    def update(self, _msg: str) -> None:
        pass


def device_info_table(raw: str) -> Table:
    table = Table(title="🐬 Flipper Zero", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")
    for key, value in parse_device_info(raw).items():
        table.add_row(key, value)
    return table


def write_results_table(results: list[tuple[int, bool]]) -> Table:
    table = Table(title="✍️  Write results", show_header=True, header_style="bold cyan")
    table.add_column("Page", justify="right")
    table.add_column("Status")
    for page, ok in results:
        status = "[success]✅ ok[/]" if ok else "[error]❌ failed[/]"
        table.add_row(str(page), status)
    return table


def verify_results_table(results: list[tuple[int, bool]]) -> Table:
    table = Table(title="🔍 Verify results", show_header=True, header_style="bold cyan")
    table.add_column("Page", justify="right")
    table.add_column("Match")
    for page, ok in results:
        status = "[success]✅ match[/]" if ok else "[error]❌ mismatch[/]"
        table.add_row(str(page), status)
    return table


def inspect_table(report: Any) -> Table:
    from flipper_nfc.nfc.inspect import TagInspect

    assert isinstance(report, TagInspect)
    table = Table(title="🏷️  Tag inspect", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    if report.uid:
        table.add_row("UID", report.uid)
    if report.cc_hex:
        cc_status = "writable" if report.cc_writable else "read-only"
        table.add_row("Capability Container (page 3)", f"{report.cc_hex} ({cc_status})")
    if report.static_lock_hex:
        lock = "set (OTP)" if report.static_lock_set else "clear"
        table.add_row("Static lock (page 2)", f"{report.static_lock_hex} — {lock}")
    if report.dynamic_lock_page is not None:
        lock = "set (OTP)" if report.dynamic_lock_set else "clear"
        table.add_row(
            f"Dynamic lock (page {report.dynamic_lock_page})",
            f"{report.dynamic_lock_hex} — {lock}",
        )
    if report.auth0 is not None:
        if report.password_protected:
            table.add_row("Password protection", report.protection_mode)
        else:
            table.add_row("Password protection", "disabled")
    if report.ndef_preview:
        table.add_row("NDEF preview", report.ndef_preview)
    for warning in report.warnings:
        table.add_row("Warning", f"[warning]{warning}[/]")
    return table

# Module-level default; replaced in dispatch() from args.
out = CliOutput()
