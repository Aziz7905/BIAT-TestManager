from apps.specs.models import SpecificationSourceType

from .csv_parser import CSVSpecificationSourceParser
from .docx_parser import DOCXSpecificationSourceParser
from .jira_parser import JiraSpecificationSourceParser
from .pdf_parser import PDFSpecificationSourceParser
from .text_parser import TextSpecificationSourceParser
from .url_parser import URLSpecificationSourceParser
from .xlsx_parser import XLSXSpecificationSourceParser


PARSER_MAP = {
    SpecificationSourceType.MANUAL: TextSpecificationSourceParser,
    SpecificationSourceType.PLAIN_TEXT: TextSpecificationSourceParser,
    SpecificationSourceType.CSV: CSVSpecificationSourceParser,
    SpecificationSourceType.XLSX: XLSXSpecificationSourceParser,
    SpecificationSourceType.PDF: PDFSpecificationSourceParser,
    SpecificationSourceType.DOCX: DOCXSpecificationSourceParser,
    SpecificationSourceType.JIRA_ISSUE: JiraSpecificationSourceParser,
    SpecificationSourceType.URL: URLSpecificationSourceParser,
    SpecificationSourceType.FILE_UPLOAD: TextSpecificationSourceParser,
}


def get_parser_for_source(source):
    parser_class = PARSER_MAP.get(source.source_type)

    if source.source_type == SpecificationSourceType.FILE_UPLOAD and source.file:
        filename = source.file.name.lower()
        if filename.endswith(".csv"):
            parser_class = CSVSpecificationSourceParser
        elif filename.endswith(".xlsx"):
            parser_class = XLSXSpecificationSourceParser
        elif filename.endswith(".pdf"):
            parser_class = PDFSpecificationSourceParser
        elif filename.endswith(".docx"):
            parser_class = DOCXSpecificationSourceParser

    if parser_class is None:
        parser_class = TextSpecificationSourceParser

    return parser_class()

