import csv
import io

from .base import (
    ParsedSourceResult,
    SpecificationSourceParseError,
    build_records_from_tabular_rows,
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

        reader = csv.reader(io.StringIO(decoded))
        raw_rows = [row for row in reader]
        if not raw_rows:
            raise SpecificationSourceParseError("The CSV file is empty.")

        records, languages, headers, header_row_number = build_records_from_tabular_rows(
            raw_rows,
            fallback_title_prefix=source.name,
        )

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "csv",
                "languages": sorted(language for language in languages if language),
                "parser_strategy": "heuristic_tabular_v2",
                "header_row": header_row_number,
            },
            column_mapping={
                "columns": headers,
            },
        )
