from .base import ParsedSourceResult, SpecificationSourceParseError, split_text_into_records


class DOCXSpecificationSourceParser:
    def parse(self, source):
        if not source.file:
            raise SpecificationSourceParseError("A DOCX file is required.")

        try:
            from docx import Document
        except ImportError as error:
            raise SpecificationSourceParseError(
                "DOCX parsing requires the python-docx package."
            ) from error

        document = Document(source.file)
        source.file.seek(0)

        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        text = "\n\n".join(paragraphs)

        return ParsedSourceResult(
            records=split_text_into_records(
                text,
                default_title=source.name,
                section_label="Document",
            ),
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "docx",
                "paragraph_count": len(paragraphs),
            },
        )

