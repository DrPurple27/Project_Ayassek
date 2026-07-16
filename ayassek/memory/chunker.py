import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    text: str
    source: str
    chunk_index: int
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "category": self.category,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, text: str, source: str, category: str = "general", **kwargs) -> list[Chunk]:
        pass


class FixedSizeChunker(BaseChunker):
    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str, source: str, category: str = "general", **kwargs) -> list[Chunk]:
        if not text.strip():
            return []

        chunks = []
        start = 0
        chunk_index = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            if end < text_len:
                last_space = text.rfind(" ", start, end)
                if last_space > start + self.min_chunk_size:
                    end = last_space

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(Chunk(
                    text=chunk_text,
                    source=source,
                    chunk_index=chunk_index,
                    category=category,
                ))
                chunk_index += 1

            if end >= text_len:
                break

            start = end - self.chunk_overlap
            if start < 0:
                start = 0

        return chunks


class MarkdownChunker(BaseChunker):
    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.fixed_chunker = FixedSizeChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
        )

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        pattern = r"^(#{1,6})\s+(.+)$"
        sections = []
        current_section = ""
        current_header = ""
        header_level = 0

        for line in text.split("\n"):
            match = re.match(pattern, line)
            if match:
                if current_section.strip():
                    sections.append((current_header, current_section.strip()))
                current_header = match.group(2).strip()
                header_level = len(match.group(1))
                current_section = line + "\n"
            else:
                current_section += line + "\n"

        if current_section.strip():
            sections.append((current_header, current_section.strip()))

        if not sections:
            sections.append(("", text))

        return sections

    def chunk(self, text: str, source: str, category: str = "general", **kwargs) -> list[Chunk]:
        if not text.strip():
            return []

        sections = self._split_by_headers(text)
        all_chunks = []
        chunk_index = 0

        for header, section_text in sections:
            section_chunks = self.fixed_chunker.chunk(
                section_text,
                source=source,
                category=category,
            )

            for chunk in section_chunks:
                chunk.chunk_index = chunk_index
                chunk.metadata["header"] = header
                all_chunks.append(chunk)
                chunk_index += 1

        return all_chunks


class SemanticChunker(BaseChunker):
    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        separators: Optional[list[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.separators = separators or [
            "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "
        ]
        self.markdown_chunker = MarkdownChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
        )

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if not separators:
            return [text]

        sep = separators[0]
        parts = text.split(sep)

        if len(parts) == 1:
            return self._recursive_split(text, separators[1:])

        result = []
        current = ""
        for part in parts:
            test = current + (sep if current else "") + part
            if len(test) <= self.chunk_size:
                current = test
            else:
                if current:
                    result.append(current)
                current = part

        if current:
            result.append(current)

        final = []
        for part in result:
            if len(part) > self.chunk_size:
                final.extend(self._recursive_split(part, separators[1:]))
            else:
                final.append(part)

        return final

    def chunk(self, text: str, source: str, category: str = "general", **kwargs) -> list[Chunk]:
        if not text.strip():
            return []

        if text.strip().startswith("#") or "\n#" in text:
            return self.markdown_chunker.chunk(text, source, category, **kwargs)

        sections = self._recursive_split(text, self.separators)
        chunks = []
        chunk_index = 0
        current_chunk = ""

        for section in sections:
            if len(current_chunk) + len(section) <= self.chunk_size:
                current_chunk += (" " if current_chunk else "") + section
            else:
                if current_chunk.strip() and len(current_chunk.strip()) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        text=current_chunk.strip(),
                        source=source,
                        chunk_index=chunk_index,
                        category=category,
                    ))
                    chunk_index += 1
                current_chunk = section

        if current_chunk.strip() and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(Chunk(
                text=current_chunk.strip(),
                source=source,
                chunk_index=chunk_index,
                category=category,
            ))

        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    prev_text = chunks[i - 1].text
                    overlap_text = prev_text[-self.chunk_overlap:] if len(prev_text) > self.chunk_overlap else prev_text
                    chunk.text = overlap_text + " " + chunk.text
                overlapped.append(chunk)
            chunks = overlapped

        return chunks


class ChunkerFactory:
    _chunker: Optional[BaseChunker] = None

    @classmethod
    def get_chunker(cls, strategy: Optional[str] = None) -> BaseChunker:
        if cls._chunker is None or strategy:
            chunk_cfg = settings.memory.rag.chunking
            strat = strategy or chunk_cfg.strategy

            if strat == "fixed":
                cls._chunker = FixedSizeChunker(
                    chunk_size=chunk_cfg.chunk_size,
                    chunk_overlap=chunk_cfg.chunk_overlap,
                    min_chunk_size=chunk_cfg.min_chunk_size,
                    max_chunk_size=chunk_cfg.max_chunk_size,
                )
            elif strat == "markdown":
                cls._chunker = MarkdownChunker(
                    chunk_size=chunk_cfg.chunk_size,
                    chunk_overlap=chunk_cfg.chunk_overlap,
                    min_chunk_size=chunk_cfg.min_chunk_size,
                    max_chunk_size=chunk_cfg.max_chunk_size,
                )
            elif strat == "semantic":
                cls._chunker = SemanticChunker(
                    chunk_size=chunk_cfg.chunk_size,
                    chunk_overlap=chunk_cfg.chunk_overlap,
                    min_chunk_size=chunk_cfg.min_chunk_size,
                    max_chunk_size=chunk_cfg.max_chunk_size,
                    separators=chunk_cfg.separators,
                )
            else:
                cls._chunker = SemanticChunker(
                    chunk_size=chunk_cfg.chunk_size,
                    chunk_overlap=chunk_cfg.chunk_overlap,
                    min_chunk_size=chunk_cfg.min_chunk_size,
                    max_chunk_size=chunk_cfg.max_chunk_size,
                    separators=chunk_cfg.separators,
                )

        return cls._chunker

    @classmethod
    def chunk_text(
        cls,
        text: str,
        source: str,
        category: str = "general",
        strategy: Optional[str] = None,
        **kwargs,
    ) -> list[Chunk]:
        chunker = cls.get_chunker(strategy)
        return chunker.chunk(text, source, category, **kwargs)