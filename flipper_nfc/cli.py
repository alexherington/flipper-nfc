"""CLI entry point for flipper-nfc."""

from __future__ import annotations

import argparse
from pathlib import Path

import serial

from flipper_nfc import __version__
from flipper_nfc.config import (
    config_path,
    resolve_connection,
    set_value,
    settings_as_dict,
    unset_value,
)
from flipper_nfc.connection import FlipperConnection, open_connection
from flipper_nfc.nfc.emulate import emulate_tag
from flipper_nfc.nfc.format import parse_nfc
from flipper_nfc.nfc.inspect import inspect_tag
from flipper_nfc.nfc.pages import PageIOError, read_page, write_page
from flipper_nfc.nfc.read import ReadError, read_tag
from flipper_nfc.nfc.write import verify_writes, write_tag
from flipper_nfc.output import (
    device_info_table,
    inspect_table,
    out,
    parse_device_info,
    verify_results_table,
    write_results_table,
)

_CONN_ERRORS = (RuntimeError, serial.SerialException, OSError)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flipper-nfc",
        description="Read and write NFC tags using a Flipper Zero over USB.",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="USB serial port (default: auto-detect, or from config)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable JSON on stdout; errors as JSON on stderr",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress progress and decorative output",
    )
    parser.add_argument("--no-color", action="store_true", help="disable coloured output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("device-info", help="print Flipper device_info")

    read_p = sub.add_parser("read", help="read an NFC tag to a .nfc file or stdout")
    read_p.add_argument(
        "-o",
        "--output",
        help="save to .nfc file (default: print to terminal)",
    )
    read_p.add_argument("--timeout", type=float, default=30.0, help="seconds to wait per attempt")
    read_p.add_argument(
        "--retries",
        type=int,
        default=3,
        help="attempts before giving up (default: 3)",
    )

    write_p = sub.add_parser("write", help="write a .nfc file to a physical tag")
    write_p.add_argument("-i", "--input", required=True, help="input .nfc path")
    write_p.add_argument(
        "--from-page",
        type=int,
        default=3,
        help="first page to write (default: 3, skips UID/lock pages)",
    )
    write_p.add_argument(
        "--verify",
        action="store_true",
        help="read back written pages and compare to the input file",
    )

    inspect_p = sub.add_parser("inspect", help="show lock, CC, password, and NDEF status")
    inspect_p.add_argument(
        "--show-mfu-info",
        action="store_true",
        help="include raw mfu info output",
    )

    read_page_p = sub.add_parser("read-page", help="read one Ultralight page (4 bytes)")
    read_page_p.add_argument("page", type=int, help="page number")

    write_page_p = sub.add_parser("write-page", help="write one Ultralight page (4 bytes)")
    write_page_p.add_argument("page", type=int, help="page number")
    write_page_p.add_argument(
        "data",
        help="4-byte page value as 8 hex digits, e.g. E1101200",
    )

    emulate_p = sub.add_parser("emulate", help="emulate a .nfc file")
    emulate_p.add_argument("-i", "--input", required=True, help="input .nfc path")
    emulate_p.add_argument(
        "--duration",
        type=float,
        help="seconds to emulate (default: until Ctrl+C)",
    )

    storage_p = sub.add_parser("storage", help="SD card storage commands")
    storage_sub = storage_p.add_subparsers(dest="storage_command", required=True)
    storage_list = storage_sub.add_parser("list", help="list files on SD path")
    storage_list.add_argument("path", help="SD path, e.g. /ext/nfc")
    storage_read = storage_sub.add_parser("read", help="read file from SD")
    storage_read.add_argument("path", help="SD file path")
    storage_read.add_argument("-o", "--output", help="save to local file")

    shell_p = sub.add_parser("shell", help="raw CLI passthrough (debug)")
    shell_p.add_argument("cmd", nargs=argparse.REMAINDER, help="command to send")

    config_p = sub.add_parser("config", help="manage saved defaults")
    config_sub = config_p.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="print effective connection settings")
    config_sub.add_parser("path", help="print config file location")
    set_p = config_sub.add_parser("set", help="save a connection default")
    set_p.add_argument("key", choices=("port",))
    set_p.add_argument("value")
    unset_p = config_sub.add_parser("unset", help="remove a saved default")
    unset_p.add_argument("key", choices=("port",))

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        raise SystemExit(0)
    try:
        apply_connection_config(args)
    except ValueError as exc:
        from flipper_nfc.output import CliOutput

        CliOutput.from_args(args).fail(str(exc))
    dispatch(args)


def apply_connection_config(args: argparse.Namespace) -> None:
    if args.command == "config":
        return
    resolved = resolve_connection(args.port)
    args.port = resolved.port


def dispatch(args: argparse.Namespace) -> None:
    global out
    from flipper_nfc.output import CliOutput

    out = CliOutput.from_args(args)

    if args.command == "config":
        cmd_config(args)
        return

    if not out.quiet and not args.json:
        out.info("Connecting via USB…")

    try:
        conn_ctx = open_connection(port=getattr(args, "port", None))
    except _CONN_ERRORS as exc:
        out.fail(str(exc))

    try:
        with conn_ctx as conn:
            if args.command == "device-info":
                cmd_device_info(conn, args)
            elif args.command == "read":
                cmd_read(conn, args)
            elif args.command == "write":
                cmd_write(conn, args)
            elif args.command == "inspect":
                cmd_inspect(conn, args)
            elif args.command == "read-page":
                cmd_read_page(conn, args)
            elif args.command == "write-page":
                cmd_write_page(conn, args)
            elif args.command == "emulate":
                cmd_emulate(conn, args)
            elif args.command == "storage":
                cmd_storage(conn, args)
            elif args.command == "shell":
                cmd_shell(conn, args)
            else:
                out.fail(f"Unknown command: {args.command}", code=2)
    except _CONN_ERRORS as exc:
        out.fail(str(exc))


def cmd_config(args: argparse.Namespace) -> None:
    if args.config_command == "path":
        if args.json:
            out.emit({"ok": True, "path": str(config_path())})
        else:
            out.print_text(str(config_path()))
        return

    if args.config_command == "show":
        resolved = resolve_connection(None)
        payload = {
            "ok": True,
            "path": str(config_path()),
            "connection": settings_as_dict(resolved),
        }
        if args.json:
            out.emit(payload)
        else:
            out.print_text(f"Config file: {payload['path']}")
            for key, value in payload["connection"].items():
                display = value if value is not None else "(not set)"
                out.print_text(f"  {key}: {display}")
        return

    if args.config_command == "set":
        try:
            set_value(args.key, args.value)
        except ValueError as exc:
            out.fail(str(exc))
        if args.json:
            out.emit({"ok": True, "key": args.key, "value": args.value, "path": str(config_path())})
        else:
            out.success(f"Saved {args.key} → [accent]{args.value}[/] in {config_path()}")
        return

    if args.config_command == "unset":
        try:
            unset_value(args.key)
        except ValueError as exc:
            out.fail(str(exc))
        if args.json:
            out.emit({"ok": True, "key": args.key, "path": str(config_path())})
        else:
            out.success(f"Removed {args.key} from {config_path()}")
        return

    out.fail(f"Unknown config command: {args.config_command}", code=2)


def cmd_device_info(conn: FlipperConnection, args: argparse.Namespace) -> None:
    raw = conn.device_info()
    info = parse_device_info(raw)
    if args.json:
        out.emit({"ok": True, "device": info})
    else:
        out.print_table(device_info_table(raw))


def cmd_read(conn: FlipperConnection, args: argparse.Namespace) -> None:
    output = Path(args.output) if args.output else None
    status_msg = (
        f"[cyan]📖[/] Hold tag on Flipper's back… "
        f"[dim](attempt 1/{args.retries}, {args.timeout:.0f}s timeout)[/]"
    )

    try:
        with out.status(status_msg) as status:

            def retry_cb(attempt: int, total: int, msg: str) -> None:
                if out.quiet:
                    return
                status.update(
                    f"[yellow]🔄[/] Retry {attempt + 1}/{total} — {msg} "
                    f"[dim]({args.timeout:.0f}s timeout)[/]"
                )

            body = read_tag(
                conn,
                output,
                timeout_sec=args.timeout,
                retries=args.retries,
                on_retry=retry_cb,
            )
    except ReadError as exc:
        if not args.json:
            out.info("Centre the tag over the coil on the Flipper's back and try again.")
        out.fail(str(exc))

    if output is not None and not output.exists():
        output.write_text(body + "\n")

    if args.json:
        dump = parse_nfc(body)
        payload: dict = {
            "ok": True,
            "uid": dump.uid,
            "device_type": dump.device_type,
            "pages": len(dump.pages),
        }
        if output is not None:
            payload["output"] = str(output)
        else:
            payload["body"] = body
        out.emit(payload)
    elif output is not None:
        out.success(f"Saved → [accent]{output}[/]")
    else:
        out.print_text(body)


def cmd_write(conn: FlipperConnection, args: argparse.Namespace) -> None:
    if not out.quiet:
        out.info("Hold a [bold]blank writable[/] NTAG on the Flipper's back…")
    with out.status("[cyan]✍️[/]  Writing pages…"):
        results = write_tag(conn, Path(args.input), from_page=args.from_page)

    failed = [p for p, ok in results if not ok]
    verified: list[tuple[int, bool]] = []
    if args.verify and not failed:
        with out.status("[cyan]🔍[/]  Verifying pages…"):
            verified = verify_writes(conn, Path(args.input), args.from_page, results)
    verify_failed = [p for p, ok in verified if not ok]

    if args.json:
        payload: dict = {
            "ok": not failed and not verify_failed,
            "pages": [{"page": p, "ok": ok} for p, ok in results],
            "failed": failed,
        }
        if args.verify:
            payload["verified"] = [{"page": p, "match": ok} for p, ok in verified]
            payload["verify_failed"] = verify_failed
        out.emit(payload)
        if failed or verify_failed:
            raise SystemExit(1)
    else:
        out.print_table(write_results_table(results))
        if failed:
            out.fail(f"Failed pages: {failed}")
        if args.verify:
            out.print_table(verify_results_table(verified))
            if verify_failed:
                out.fail(f"Verify mismatches: {verify_failed}")
            out.success("Write verified")


def cmd_inspect(conn: FlipperConnection, args: argparse.Namespace) -> None:
    if not out.quiet:
        out.info("Hold the tag on the Flipper's back…")
    try:
        with out.status("[cyan]🔍[/]  Reading tag…"):
            report = inspect_tag(conn)
    except PageIOError as exc:
        out.fail(str(exc))

    if args.json:
        payload = {"ok": True, **report.to_dict()}
        if getattr(args, "show_mfu_info", False):
            payload["mfu_info"] = report.mfu_info
        out.emit(payload)
    else:
        out.print_table(inspect_table(report))
        if getattr(args, "show_mfu_info", False) and report.mfu_info.strip():
            out.print_text(report.mfu_info.rstrip())


def cmd_read_page(conn: FlipperConnection, args: argparse.Namespace) -> None:
    if not out.quiet:
        out.info("Hold the tag on the Flipper's back…")
    try:
        with out.status(f"[cyan]📄[/]  Reading page {args.page}…"):
            data = read_page(conn, args.page)
    except PageIOError as exc:
        out.fail(str(exc))

    spaced = " ".join(f"{b:02X}" for b in data)
    if args.json:
        out.emit({"ok": True, "page": args.page, "data": data.hex().upper(), "hex": spaced})
    else:
        out.print_text(f"Page {args.page}: {spaced}")


def cmd_write_page(conn: FlipperConnection, args: argparse.Namespace) -> None:
    if not out.quiet:
        out.info("Hold a [bold]blank writable[/] NTAG on the Flipper's back…")
    try:
        with out.status(f"[cyan]✍️[/]  Writing page {args.page}…"):
            write_page(conn, args.page, args.data)
    except PageIOError as exc:
        out.fail(str(exc))

    if args.json:
        out.emit({"ok": True, "page": args.page, "data": args.data.replace(" ", "").upper()})
    else:
        out.success(f"Page {args.page} written")


def cmd_emulate(conn: FlipperConnection, args: argparse.Namespace) -> None:
    if not out.quiet:
        if args.duration:
            out.info(f"Emulating for {args.duration:.0f}s…")
        else:
            out.info("Emulating — press [bold]Ctrl+C[/] to stop")

    with out.status("[cyan]🎭[/]  Emulating NFC tag…"):
        emulate_tag(conn, Path(args.input), duration_sec=args.duration)

    if args.json:
        out.emit({"ok": True, "input": args.input, "duration": args.duration})
    else:
        out.success("Emulation stopped")


def cmd_storage(conn: FlipperConnection, args: argparse.Namespace) -> None:
    if args.storage_command == "list":
        raw = conn.storage_list(args.path)
        if args.json:
            out.emit({"ok": True, "path": args.path, "listing": raw})
        else:
            out.print_text(raw)
    elif args.storage_command == "read":
        body = conn.storage_read(args.path)
        if args.output:
            out_path = Path(args.output)
            out_path.write_text(body + "\n")
            if args.json:
                out.emit({"ok": True, "path": args.path, "output": str(out_path)})
            else:
                out.success(f"Saved → [accent]{args.output}[/]")
        elif args.json:
            out.emit({"ok": True, "path": args.path, "body": body})
        else:
            out.print_text(body)
    else:
        out.fail(f"Unknown storage command: {args.storage_command}", code=2)


def cmd_shell(conn: FlipperConnection, args: argparse.Namespace) -> None:
    cmd = " ".join(args.cmd).strip()
    if not cmd:
        out.fail("shell: provide a command", code=2)
    raw = conn.send_raw(cmd, wait=2.0)
    if args.json:
        out.emit({"ok": True, "command": cmd, "response": raw})
    else:
        out.print_text(raw)


if __name__ == "__main__":
    main()
