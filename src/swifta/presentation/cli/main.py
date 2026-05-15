"""CLI application."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

from swifta.application.control_flow import (
    BuildNassiDiagramCommand,
    BuildNassiDirectoryCommand,
    NassiDiagramBundleDTO,
    NassiDiagramService,
)
from swifta.application.dto import ParseDirectoryCommand, ParseFileCommand, ParsingJobReportDTO
from swifta.application.use_cases import ParsingJobService
from swifta.domain.errors import SwiftaError
from swifta.infrastructure.antlr.control_flow_extractor import AntlrSwiftControlFlowExtractor
from swifta.infrastructure.antlr.parser_adapter import AntlrSwiftSyntaxParser
from swifta.infrastructure.filesystem.source_repository import FileSystemSourceRepository
from swifta.infrastructure.rendering.nassi_html_renderer import HtmlNassiDiagramRenderer
from swifta.infrastructure.system import (
    InMemoryParsingJobRepository,
    StructuredLoggingEventPublisher,
    SystemClock,
    configure_logging,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    configure_logging(verbose=getattr(args, "verbose", False))

    try:
        if args.command == "parse-file":
            report = _build_parse_service().parse_file(ParseFileCommand(path=args.path))
        elif args.command == "parse-dir":
            report = _build_parse_service().parse_directory(
                ParseDirectoryCommand(root_path=args.path)
            )
        elif args.command == "nassi-file":
            document = _build_nassi_service().build_file_diagram(
                BuildNassiDiagramCommand(path=args.path)
            )
            output_path = _resolve_output_path(args.path, args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(document.html, encoding="utf-8")

            payload = document.to_dict()
            payload["output_path"] = str(output_path)
            print(json.dumps(payload, indent=2))
            return 0
        elif args.command == "nassi-dir":
            bundle = _build_nassi_service().build_directory_diagrams(
                BuildNassiDirectoryCommand(root_path=args.path)
            )
            output_dir = _resolve_output_directory(args.path, args.out)
            written_diagrams = _write_directory_diagrams(bundle, output_dir)
            index_path = output_dir / "index.html"
            index_path.write_text(
                _render_directory_index(bundle.root_path, written_diagrams),
                encoding="utf-8",
            )

            payload = bundle.to_dict()
            payload["output_dir"] = str(output_dir)
            payload["index_path"] = str(index_path)
            payload["documents"] = [
                {
                    "source_location": diagram.source_location,
                    "function_count": diagram.function_count,
                    "function_names": list(diagram.function_names),
                    "output_path": str(diagram.output_path),
                    "relative_output_path": diagram.relative_output_path,
                }
                for diagram in written_diagrams
            ]
            print(json.dumps(payload, indent=2))
            return 0
        else:
            parser.error(f"unsupported command: {args.command}")
    except SwiftaError as error:
        print(json.dumps({"error": str(error)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(report.to_dict(), indent=2))
    return _exit_code_for(report)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse Swift source code with ANTLR.")
    parser.add_argument("--verbose", action="store_true", help="Enable lifecycle logging.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_file = subparsers.add_parser("parse-file", help="Parse one Swift file.")
    parse_file.add_argument("path", help="Path to a .swift file.")

    parse_dir = subparsers.add_parser("parse-dir", help="Parse all Swift files in a directory.")
    parse_dir.add_argument("path", help="Path to a directory.")

    nassi_file = subparsers.add_parser(
        "nassi-file",
        help="Build a Nassi-Shneiderman HTML diagram for one Swift file.",
    )
    nassi_file.add_argument("path", help="Path to a .swift file.")
    nassi_file.add_argument(
        "--out",
        help="Output HTML path. Defaults to <input>.nassi.html.",
    )

    nassi_dir = subparsers.add_parser(
        "nassi-dir",
        help="Build Nassi-Shneiderman HTML diagrams for all Swift files in a directory.",
    )
    nassi_dir.add_argument("path", help="Path to a directory.")
    nassi_dir.add_argument(
        "--out",
        help="Output directory. Defaults to <input>.nassi/.",
    )
    return parser


def _build_parse_service() -> ParsingJobService:
    return ParsingJobService(
        source_repository=FileSystemSourceRepository(),
        parser=AntlrSwiftSyntaxParser(),
        event_publisher=StructuredLoggingEventPublisher(),
        clock=SystemClock(),
        job_repository=InMemoryParsingJobRepository(),
    )


def _build_nassi_service() -> NassiDiagramService:
    return NassiDiagramService(
        source_repository=FileSystemSourceRepository(),
        extractor=AntlrSwiftControlFlowExtractor(),
        renderer=HtmlNassiDiagramRenderer(),
    )


def _exit_code_for(report: ParsingJobReportDTO) -> int:
    if report.summary.technical_failure_count > 0:
        return 1
    return 0


def _resolve_output_path(input_path: str, explicit_output_path: str | None) -> Path:
    if explicit_output_path:
        return Path(explicit_output_path).expanduser().resolve()

    resolved_input = Path(input_path).expanduser().resolve()
    return resolved_input.with_suffix(".nassi.html")


def _resolve_output_directory(input_path: str, explicit_output_path: str | None) -> Path:
    if explicit_output_path:
        return Path(explicit_output_path).expanduser().resolve()

    resolved_input = Path(input_path).expanduser().resolve()
    return resolved_input.with_name(f"{resolved_input.name}.nassi")


@dataclass(frozen=True, slots=True)
class _WrittenNassiDiagram:
    source_location: str
    function_count: int
    function_names: tuple[str, ...]
    output_path: Path
    relative_output_path: str
    relative_source_path: str


def _write_directory_diagrams(
    bundle: NassiDiagramBundleDTO,
    output_dir: Path,
) -> tuple[_WrittenNassiDiagram, ...]:
    root_path = Path(bundle.root_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    written_diagrams: list[_WrittenNassiDiagram] = []
    for document in bundle.documents:
        source_path = Path(document.source_location)
        relative_source_path = source_path.relative_to(root_path)
        output_path = (output_dir / relative_source_path).with_suffix(".nassi.html")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document.html, encoding="utf-8")
        written_diagrams.append(
            _WrittenNassiDiagram(
                source_location=document.source_location,
                function_count=document.function_count,
                function_names=document.function_names,
                output_path=output_path,
                relative_output_path=output_path.relative_to(output_dir).as_posix(),
                relative_source_path=relative_source_path.as_posix(),
            )
        )
    return tuple(written_diagrams)


def _render_directory_index(
    root_path: str,
    written_diagrams: tuple[_WrittenNassiDiagram, ...],
) -> str:
    rows = "".join(
        (
            "<tr>"
            f'<td><a href="{escape(diagram.relative_output_path)}">{escape(diagram.relative_source_path)}</a></td>'
            f"<td>{diagram.function_count}</td>"
            f"<td>{escape(', '.join(diagram.function_names) if diagram.function_names else '—')}</td>"
            "</tr>"
        )
        for diagram in written_diagrams
    )
    if not rows:
        rows = '<tr><td colspan="3">No diagrams were generated.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Swifta NSD Index</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
      :root {{
        --bg:          #f8fafc;
        --surface:     #ffffff;
        --surface-2:   #f1f5f9;
        --border:      #e2e8f0;
        --border-strong: #cbd5e1;
        --text:        #0f172a;
        --text-muted:  #64748b;
        --primary:     #2563eb;
        --primary-dark: #1d4ed8;
        --shadow-sm:   0 1px 2px rgba(0, 0, 0, 0.05);
        --shadow-md:   0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        --radius:      12px;
        --font-ui: "IBM Plex Sans", -apple-system, "Segoe UI", system-ui, sans-serif;
        --font-mono: "JetBrains Mono", "Fira Code", "SFMono-Regular", monospace;
      }}

      * {{ box-sizing: border-box; margin: 0; padding: 0; }}

      body {{
        margin: 0;
        padding: 40px 24px;
        font-family: var(--font-ui);
        font-size: 15px;
        color: var(--text);
        background: linear-gradient(180deg, #f1f5f9 0%, var(--bg) 100%);
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
      }}

      .container {{
        max-width: 1000px;
        margin: 0 auto;
      }}

      .header {{
        margin-bottom: 28px;
      }}

      .header h1 {{
        font-size: 28px;
        font-weight: 600;
        color: var(--text);
        margin: 0 0 6px;
        letter-spacing: -0.02em;
      }}

      .header p {{
        color: var(--text-muted);
        font-size: 14px;
        margin: 0;
        font-family: var(--font-mono);
      }}

      .card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow-md);
        overflow: hidden;
      }}

      .card-header {{
        padding: 16px 20px;
        background: linear-gradient(180deg, var(--surface-2) 0%, var(--surface) 100%);
        border-bottom: 1px solid var(--border);
        font-family: var(--font-mono);
        font-size: 12px;
        font-weight: 500;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }}

      .card-body {{
        padding: 4px;
      }}

      .table-wrapped {{
        overflow-x: auto;
      }}

      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
      }}

      th {{
        text-align: left;
        padding: 12px 16px;
        font-weight: 600;
        color: var(--text-muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        border-bottom: 1px solid var(--border);
        background: var(--surface-2);
      }}

      td {{
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        vertical-align: top;
      }}

      tr:last-child td {{
        border-bottom: 0;
      }}

      tr:hover td {{
        background: var(--surface-2);
      }}

      a {{
        color: var(--primary);
        text-decoration: none;
        font-weight: 500;
        transition: color 0.15s;
      }}

      a:hover {{
        color: var(--primary-dark);
        text-decoration: underline;
      }}

      .count {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        height: 28px;
        font-size: 13px;
        font-weight: 600;
        font-family: var(--font-mono);
        background: var(--surface-2);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text-muted);
      }}

      .count.zero {{
        color: #94a3b8;
        background: #f1f5f9;
      }}

      .names {{
        font-family: var(--font-mono);
        font-size: 13px;
        line-height: 1.6;
        color: var(--text-muted);
      }}

      .empty {{
        color: var(--text-muted);
        font-style: italic;
      }}

      @media (max-width: 640px) {{
        body {{ padding: 20px 16px; }}
        .header h1 {{ font-size: 22px; }}
        th, td {{ padding: 10px 12px; }}
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <div class="header">
        <h1>Nassi-Shneiderman Diagrams</h1>
        <p>{escape(root_path)}</p>
      </div>
      <div class="card">
        <div class="card-header">{len(written_diagrams)} file(s)</div>
        <div class="card-body">
          <div class="table-wrapped">
            <table>
              <thead>
                <tr>
                  <th>Source File</th>
                  <th style="width: 120px;">Functions</th>
                  <th>Functions Found</th>
                </tr>
              </thead>
              <tbody>
                {rows}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
