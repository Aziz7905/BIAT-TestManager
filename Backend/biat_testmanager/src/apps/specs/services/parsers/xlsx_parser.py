from .base import (
    ParsedSourceResult,
    SpecificationSourceParseError,
    build_records_from_tabular_rows,
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

            (
                sheet_records,
                sheet_languages,
                sheet_headers,
                header_row_number,
            ) = build_records_from_tabular_rows(
                rows,
                fallback_title_prefix=sheet.title,
                default_section_label=sheet.title,
            )
            column_mapping[sheet.title] = sheet_headers
            records.extend(sheet_records)
            languages.update(sheet_languages)
            if header_row_number is not None:
                for record in sheet_records:
                    record.record_metadata["sheet_name"] = sheet.title
                    record.record_metadata["sheet_header_row"] = header_row_number
            else:
                for record in sheet_records:
                    record.record_metadata["sheet_name"] = sheet.title

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "xlsx",
                "sheet_count": len(workbook.worksheets),
                "languages": sorted(language for language in languages if language),
                "parser_strategy": "heuristic_tabular_v2",
            },
            column_mapping=column_mapping,
        )
