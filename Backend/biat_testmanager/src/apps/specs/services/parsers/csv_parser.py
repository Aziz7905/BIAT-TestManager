import csv
import io

from .base import ParsedSourceResult, SpecificationSourceParseError, clean_text
from .tabular_structure import (
    GridCell,
    build_records_for_region,
    column_to_letter,
    segment_regions,
    trim_empty_grid,
)

CSV_CONTAINER = "CSV"


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
        raw_rows = list(reader)
        if not raw_rows:
            raise SpecificationSourceParseError("The CSV file is empty.")

        grid = trim_empty_grid(_build_grid(raw_rows))

        records = []
        regions_descriptor: list[dict] = []
        for region in segment_regions(grid, container=CSV_CONTAINER):
            region_records, region_metadata = build_records_for_region(region)
            records.extend(region_records)
            regions_descriptor.append(
                {
                    **region_metadata,
                    "needs_mapping": region_metadata["structural_type"] == "table",
                }
            )

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "csv",
                "parser_strategy": "structural_grid_v1",
                "region_count": len(regions_descriptor),
            },
            column_mapping={"regions": regions_descriptor},
        )


def _build_grid(raw_rows: list[list[str]]) -> list[list[GridCell]]:
    grid: list[list[GridCell]] = []
    for row_index, row in enumerate(raw_rows, start=1):
        row_cells: list[GridCell] = []
        for column_index, value in enumerate(row, start=1):
            cleaned = clean_text(value)
            row_cells.append(
                GridCell(
                    row=row_index,
                    column=column_index,
                    coordinate=f"{column_to_letter(column_index)}{row_index}",
                    raw_value=cleaned,
                    displayed_value=cleaned,
                )
            )
        grid.append(row_cells)
    return grid
