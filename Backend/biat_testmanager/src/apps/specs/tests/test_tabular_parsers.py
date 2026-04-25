from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.specs.services.parsers.csv_parser import CSVSpecificationSourceParser
from apps.specs.services.parsers.xlsx_parser import XLSXSpecificationSourceParser


class TabularSpecificationSourceParserTests(SimpleTestCase):
    def test_csv_parser_detects_offset_header_and_section_context_rows(self):
        payload = BytesIO(
            (
                "Specification export,,,\n"
                "Reference,Title,Description,Section\n"
                ",,,Claims processing\n"
                "REQ-001,Select eligible claims,Select claims with pending status,\n"
                "Reference,Title,Description,Section\n"
                "REQ-002,Generate invoices,Generate invoice file,\n"
            ).encode("utf-8")
        )
        payload.name = "sample.csv"

        source = SimpleNamespace(name="Sample CSV", file=payload)

        result = CSVSpecificationSourceParser().parse(source)

        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.source_metadata["header_row"], 2)
        self.assertEqual(result.column_mapping["columns"], ["Reference", "Title", "Description", "Section"])
        self.assertEqual(result.records[0].external_reference, "REQ-001")
        self.assertEqual(result.records[0].section_label, "Claims processing")
        self.assertEqual(result.records[1].section_label, "Claims processing")

    def test_xlsx_parser_detects_headers_after_intro_rows_and_skips_repeated_headers(self):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Invoices"
        sheet.append(["Generated export"])
        sheet.append([])
        sheet.append(["ID", "Feature", "Preconditions", "Steps", "Expected Result"])
        sheet.append(["Settlement flow"])
        sheet.append(["RX-01", "Prepare settlement", "Claims exist", "Open job screen", "Settlement is generated"])
        sheet.append(["ID", "Feature", "Preconditions", "Steps", "Expected Result"])
        sheet.append(["RX-02", "Review settlement", "", "Open generated file", "Data is visible"])

        payload = BytesIO()
        workbook.save(payload)
        payload.seek(0)
        payload.name = "sample.xlsx"

        source = SimpleNamespace(name="Sample XLSX", file=payload)

        result = XLSXSpecificationSourceParser().parse(source)

        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.column_mapping["Invoices"], ["ID", "Feature", "Preconditions", "Steps", "Expected Result"])
        self.assertEqual(result.records[0].title, "Prepare settlement")
        self.assertEqual(result.records[0].external_reference, "RX-01")
        self.assertEqual(result.records[0].section_label, "Settlement flow")
        self.assertEqual(result.records[0].record_metadata["sheet_header_row"], 3)
        self.assertEqual(result.records[1].section_label, "Settlement flow")
