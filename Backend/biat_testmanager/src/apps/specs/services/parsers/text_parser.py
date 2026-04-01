from .base import ParsedSourceResult, SpecificationSourceParseError, split_text_into_records


class TextSpecificationSourceParser:
    def parse(self, source):
        text = source.raw_text.strip()
        if not text and source.file:
            text = source.file.read().decode("utf-8", errors="ignore").strip()
            source.file.seek(0)

        if not text:
            raise SpecificationSourceParseError("Text content is required.")

        return ParsedSourceResult(
            records=split_text_into_records(
                text,
                default_title=source.name,
                section_label="Text",
            ),
            source_metadata={"format": "text"},
        )

