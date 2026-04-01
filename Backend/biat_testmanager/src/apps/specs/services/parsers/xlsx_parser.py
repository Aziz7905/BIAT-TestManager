from .base import (
    ParsedSourceRecord,
    ParsedSourceResult,
    SpecificationSourceParseError,
    build_reference_from_row,
    build_title_from_row,
    row_to_content,
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

                title = build_title_from_row(row, f"{sheet.title} row {row_offset}")
                records.append(
                    ParsedSourceRecord(
                        title=title,
                        content=row_to_content(row, ignore_keys=["title", "summary", "name"]),
                        external_reference=build_reference_from_row(row),
                        section_label=sheet.title,
                        row_number=row_offset,
                        record_metadata=row,
                    )
                )

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "xlsx",
                "sheet_count": len(workbook.worksheets),
            },
            column_mapping=column_mapping,
        )

