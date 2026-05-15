"""Ports owned by the inner layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from typescripta.domain.control_flow import ControlFlowDiagram
from typescripta.domain.events import DomainEvent
from typescripta.domain.model import (
    CodeSmell,
    GrammarVersion,
    ParseOutcome,
    ParsingJob,
    SourceUnit,
)


class SourceRepository(ABC):
    @abstractmethod
    def load_file(self, path: str) -> SourceUnit:
        raise NotImplementedError

    @abstractmethod
    def list_typescript_sources(
        self,
        root_path: str,
        ignore_folders: Sequence[str] = (),
        ignore_files: Sequence[str] = (),
        ignore_tests: bool = False,
    ) -> Sequence[SourceUnit]:
        raise NotImplementedError

    @abstractmethod
    def is_dir(self, path: str) -> bool:
        raise NotImplementedError


class ParsingJobRepository(ABC):
    @abstractmethod
    def save(self, job: ParsingJob) -> None:
        raise NotImplementedError


class TypeScriptSyntaxParser(ABC):
    @property
    @abstractmethod
    def grammar_version(self) -> GrammarVersion:
        raise NotImplementedError

    @abstractmethod
    def parse(self, source_unit: SourceUnit) -> ParseOutcome:
        raise NotImplementedError


class TypeScriptControlFlowExtractor(ABC):
    @abstractmethod
    def extract(self, source_unit: SourceUnit) -> ControlFlowDiagram:
        raise NotImplementedError


class CodeSmellDetector(ABC):
    @abstractmethod
    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        raise NotImplementedError


class NassiDiagramRenderer(ABC):
    @abstractmethod
    def render(self, diagram: ControlFlowDiagram) -> str:
        raise NotImplementedError


class DomainEventPublisher(ABC):
    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        raise NotImplementedError
