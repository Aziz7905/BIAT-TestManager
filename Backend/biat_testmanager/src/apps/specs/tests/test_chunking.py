from django.test import SimpleTestCase, override_settings

from apps.specs.models import SpecChunkType
from apps.specs.services.chunking import (
    build_chunks_from_content,
    infer_chunk_type,
)


class SpecificationChunkingTests(SimpleTestCase):
    def test_context_is_carried_into_following_business_rule_chunks(self):
        content = (
            "Contexte: 1/Creer un nouveau job ENTREPRISE.INTR.GF.001.JOB.RX\n\n"
            "- Selectionner les records de la table ENTREPRISE.CORR.CHRG.PARAM\n"
            "- Obtenir la liste des claims a traiter par devise et par compagnie RXT"
        )

        chunks = build_chunks_from_content(content)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].content, "Contexte: 1/Creer un nouveau job ENTREPRISE.INTR.GF.001.JOB.RX")
        self.assertIn("Contexte: 1/Creer un nouveau job", chunks[1].content)
        self.assertIn("Selectionner les records", chunks[1].content)
        self.assertEqual(chunks[1].chunk_type, SpecChunkType.FUNCTIONAL_REQUIREMENT)

    @override_settings(SPEC_CHUNK_MAX_CHARS=180, SPEC_CHUNK_OVERLAP_CHARS=45)
    def test_line_aware_chunks_do_not_cut_table_rows_mid_line(self):
        content = (
            "Table:\n"
            "- ENTREPRISE\n"
            "- D.B.O / D.T\n"
            "- REMISE DOCUMENTAIRE EXPORT TUNIS\n"
            "- ETAT D'INSTANCE DES FRAIS RECLAMES AUX CORRESPENDANTS EDITE LE Y.TODAY[7 | 2]\n"
            "- PERIODE : Y.DEBUT.PERIODE - Y.FIN.PERIODE\n"
            "- CODE ET NOM DU CORRESPONDANT : R.CUSTOMER<EB.CUS.NAME.1>\n"
            "- DEVISE : Y.DEVISE.FACTURE\n"
            "- DATE DE | NOTRE | REFERENCE DU | MONTANT"
        )

        chunks = build_chunks_from_content(content)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertNotIn("CORRESPONDANT :\n", chunk.content)
            self.assertLessEqual(len(chunk.content), 260)
        self.assertTrue(all("Table:" in chunk.content for chunk in chunks[:1]))

    def test_french_business_phrases_are_treated_as_functional_requirements(self):
        chunk_type = infer_chunk_type(
            "- Si le champ ENVOI.PAR = EXCEL donc GENERATION.EXCEL\n"
            "- A la generation de la facture RXT il y a lieu d'alimenter LAST.FREQ.RXT"
        )

        self.assertEqual(chunk_type, SpecChunkType.FUNCTIONAL_REQUIREMENT)

    def test_component_tag_skips_context_prefix(self):
        content = (
            "Contexte: 1/Create billing job\n\n"
            "- Generate invoice output for RXT"
        )

        chunks = build_chunks_from_content(content)

        self.assertEqual(chunks[1].component_tag, "generate-invoice-output-for-rxt")
