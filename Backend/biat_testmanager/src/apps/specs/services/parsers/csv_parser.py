import csv
import io

from .base import (
    ParsedSourceResult,
    SpecificationSourceParseError,
    build_record_from_row,
)


class CSVSpecificationSourceParser:
    def parse(self, source):
        if not source.file:
            raise SpecificationSourceParseError("A CSV file is required.")

        try:
            decoded = source.file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            source.file.seek(0)
            decoded = source.file.read().decode("latin-1")
        finally:
            source.file.seek(0)

        reader = csv.DictReader(io.StringIO(decoded))
        if not reader.fieldnames:
            raise SpecificationSourceParseError("The CSV file does not contain headers.")

        records = []
        languages: set[str] = set()
        for index, row in enumerate(reader):
            if not any(str(value).strip() for value in row.values() if value is not None):
                continue

            record = build_record_from_row(
                row,
                fallback_title=f"{source.name} row {index + 1}",
                row_number=index + 2,
            )
            languages.add(record.record_metadata.get("language", "unknown"))
            records.append(record)

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "csv",
                "languages": sorted(language for language in languages if language),
                "parser_strategy": "structured_tabular_v1",
            },
            column_mapping={
                "columns": [field for field in reader.fieldnames if field],
            },
        )
