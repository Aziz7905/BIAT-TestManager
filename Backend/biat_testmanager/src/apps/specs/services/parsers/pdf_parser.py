from .base import ParsedSourceResult, SpecificationSourceParseError, split_text_into_records


class PDFSpecificationSourceParser:
    def parse(self, source):
        if not source.file:
            raise SpecificationSourceParseError("A PDF file is required.")

        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise SpecificationSourceParseError(
                "PDF parsing requires the pypdf package."
            ) from error

        reader = PdfReader(source.file)
        source.file.seek(0)

        pages = []
        for index, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((index + 1, text))

        records = []
        for page_number, page_text in pages:
            records.extend(
                split_text_into_records(
                    page_text,
                    default_title=f"{source.name} page {page_number}",
                    section_label=f"Page {page_number}",
                )
            )

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "pdf",
                "page_count": len(reader.pages),
            },
        )

