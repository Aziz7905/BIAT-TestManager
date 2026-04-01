import csv
import io

from .base import (
    ParsedSourceRecord,
    ParsedSourceResult,
    SpecificationSourceParseError,
    build_reference_from_row,
    build_title_from_row,
    row_to_content,
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
        for index, row in enumerate(reader):
            if not any(str(value).strip() for value in row.values() if value is not None):
                continue

            title = build_title_from_row(row, f"{source.name} row {index + 1}")
            records.append(
                ParsedSourceRecord(
                    title=title,
                    content=row_to_content(row, ignore_keys=["title", "summary", "name"]),
                    external_reference=build_reference_from_row(row),
                    row_number=index + 2,
                    record_metadata=row,
                )
            )

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "csv",
            },
            column_mapping={
                "columns": [field for field in reader.fieldnames if field],
            },
        )

