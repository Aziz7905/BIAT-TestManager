from .base import (
    ParsedSourceResult,
    SpecificationSourceParseError,
    build_record_from_row,
)


class XLSXSpecificationSourceParser:
    def parse(self, source):
        if not source.file:
            raise SpecificationSourceParseError("An XLSX file is required.")

        try:
            from openpyxl import load_workbook
        except ImportError as error:
            raise SpecificationSourceParseError(
                "XLSX parsing requires the openpyxl package."
            ) from error

        workbook = load_workbook(filename=source.file, data_only=True)
        source.file.seek(0)

        records = []
        column_mapping: dict[str, list[str]] = {}
        languages: set[str] = set()

        for sheet in workbook.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue

            headers = [str(value).strip() if value is not None else "" for value in rows[0]]
            column_mapping[sheet.title] = [header for header in headers if header]

            for row_offset, row_values in enumerate(rows[1:], start=2):
                row = {
                    headers[index] or f"column_{index + 1}": value
                    for index, value in enumerate(row_values)
                }
                if not any(str(value).strip() for value in row.values() if value is not None):
                    continue

                record = build_record_from_row(
                    row,
                    fallback_title=f"{sheet.title} row {row_offset}",
                    default_section_label=sheet.title,
                    row_number=row_offset,
                )
                languages.add(record.record_metadata.get("language", "unknown"))
                records.append(record)

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "xlsx",
                "sheet_count": len(workbook.worksheets),
                "languages": sorted(language for language in languages if language),
                "parser_strategy": "structured_tabular_v1",
            },
            column_mapping=column_mapping,
        )
