import json
import subprocess
import sys
from pathlib import Path

from typescripta.application.dto import ParseDirectoryCommand, ParseFileCommand
from typescripta.application.use_cases import ParsingJobService
from typescripta.infrastructure.antlr.parser_adapter import AntlrTypeScriptSyntaxParser
from typescripta.infrastructure.filesystem.source_repository import FileSystemSourceRepository
from typescripta.infrastructure.system import (
    InMemoryParsingJobRepository,
    StructuredLoggingEventPublisher,
    SystemClock,
)


ROOT = Path(__file__).resolve().parent.parent


def _ensure_generated_parser() -> None:
    generated_parser = (
        ROOT / "src" / "typescripta" / "infrastructure" / "antlr" / "generated" / "typescript" / "TypeScriptParser.py"
    )
    if generated_parser.exists():
        return
    subprocess.run(
        [sys.executable, "scripts/generate_typescript_parser.py"],
        cwd=ROOT,
        check=True,
    )


def _build_service() -> ParsingJobService:
    _ensure_generated_parser()
    return ParsingJobService(
        source_repository=FileSystemSourceRepository(),
        parser=AntlrTypeScriptSyntaxParser(),
        event_publisher=StructuredLoggingEventPublisher(),
        clock=SystemClock(),
        job_repository=InMemoryParsingJobRepository(),
    )


def test_parse_file_extracts_structure() -> None:
    service = _build_service()
    report = service.parse_file(ParseFileCommand(path=str(ROOT / "tests" / "fixtures" / "valid.ts")))

    assert report.summary.source_count == 1
    assert report.summary.technical_failure_count == 0
    assert report.sources[0].status in {"succeeded", "succeeded_with_diagnostics"}
    assert {element.kind for element in report.sources[0].structural_elements} >= {
        "import",
        "class",
        "function",
        "namespace",
    }


def test_parse_directory_returns_report_for_all_files() -> None:
    service = _build_service()
    report = service.parse_directory(ParseDirectoryCommand(root_path=str(ROOT / "tests" / "fixtures")))

    assert report.summary.source_count == 3
    assert len(report.sources) == 3


def test_parse_file_handles_enum_declaration(tmp_path: Path) -> None:
    service = _build_service()
    source_path = tmp_path / "enum_parse.ts"
    source_path.write_text(
        """
enum Mode {
    Active = "active",
    Inactive = "inactive",
}

function getTitle(): string {
    return "active";
}
""".strip(),
        encoding="utf-8",
    )

    report = service.parse_file(ParseFileCommand(path=str(source_path)))

    assert report.summary.source_count == 1
    assert report.summary.technical_failure_count == 0
    assert {element.kind for element in report.sources[0].structural_elements} >= {"enum", "function"}


def test_cli_outputs_json() -> None:
    _ensure_generated_parser()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "typescripta.presentation.cli.main",
            "parse-file",
            str(ROOT / "tests" / "fixtures" / "valid.ts"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["source_count"] == 1
