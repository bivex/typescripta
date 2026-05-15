"""Filesystem implementation of source discovery and loading."""

from __future__ import annotations

from pathlib import Path

from typescripta.domain.errors import InputValidationError, SourceAccessError
from typescripta.domain.model import SourceUnit, SourceUnitId
from typescripta.domain.ports import SourceRepository


class FileSystemSourceRepository(SourceRepository):
    _EXTENSIONS = (".ts", ".tsx")

    def load_file(self, path: str) -> SourceUnit:
        source_path = Path(path).expanduser().resolve()
        if not source_path.exists():
            raise InputValidationError(f"source file does not exist: {source_path}")
        if not source_path.is_file():
            raise InputValidationError(f"path is not a file: {source_path}")
        if source_path.suffix not in self._EXTENSIONS:
            raise InputValidationError(
                f"expected a TypeScript file ({', '.join(self._EXTENSIONS)}), got: {source_path}"
            )

        return self._load_source_unit(source_path)

    def list_typescript_sources(
        self, root_path: str, ignore_folders: Sequence[str] = ()
    ) -> tuple[SourceUnit, ...]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            raise InputValidationError(f"source directory does not exist: {root}")
        if not root.is_dir():
            raise InputValidationError(f"path is not a directory: {root}")

        ignore_set = set(ignore_folders)
        source_paths: list[Path] = []

        def _collect(current: Path) -> None:
            if current.name in ignore_set:
                return

            # Add files in current directory
            for ext in self._EXTENSIONS:
                for file_path in current.glob(f"*{ext}"):
                    if file_path.is_file():
                        source_paths.append(file_path)

            # Recurse into subdirectories
            try:
                for item in current.iterdir():
                    if item.is_dir():
                        _collect(item)
            except OSError:
                # Skip directories we can't access
                pass

        _collect(root)
        source_paths.sort()

        if not source_paths:
            raise InputValidationError(f"no TypeScript files found under: {root}")

        return tuple(self._load_source_unit(path) for path in source_paths)

    def is_dir(self, path: str) -> bool:
        return Path(path).expanduser().resolve().is_dir()

    def _load_source_unit(self, path: Path) -> SourceUnit:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            raise SourceAccessError(f"unable to read source file {path}: {error}") from error
        except UnicodeDecodeError as error:
            raise SourceAccessError(f"source file is not valid UTF-8 {path}: {error}") from error

        normalized = str(path)
        return SourceUnit(
            identifier=SourceUnitId(normalized),
            location=normalized,
            content=content,
        )
