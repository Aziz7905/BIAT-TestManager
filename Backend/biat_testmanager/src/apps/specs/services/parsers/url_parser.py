from .base import ParsedSourceRecord, ParsedSourceResult, SpecificationSourceParseError


class URLSpecificationSourceParser:
    def parse(self, source):
        if not source.source_url:
            raise SpecificationSourceParseError("A source URL is required.")

        content = source.raw_text.strip() or f"Imported URL source {source.source_url}"

        record = ParsedSourceRecord(
            title=source.name or source.source_url,
            content=content,
            section_label="URL",
            record_metadata={"source_url": source.source_url},
        )

        return ParsedSourceResult(
            records=[record],
            source_metadata={
                "format": "url",
                "source_url": source.source_url,
            },
        )

