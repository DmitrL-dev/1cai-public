"""Pure byte-contract cases; no model, MCP, analyzer, or platform execution."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "managed_repair_verifier", ROOT / "scripts/verification/verify_managed_repair.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)
FIXTURE = (ROOT / "packaging/test-profiles/yaxunit-25.12/СохранитьДокумент.bsl").read_bytes()
BOM = b"\xef\xbb\xbf"


def candidate(original, statement="ВызватьИсключение;", newline=b"\n"):
    marker = "    Исключение".encode("utf-8") + newline
    return original.replace(
        marker, marker + b"        " + statement.encode("utf-8") + newline
    )


class ManagedRepairSemanticContract(unittest.TestCase):
    def test_exact_rethrow_preserves_each_supported_byte_form(self):
        for newline in (b"\n", b"\r\n"):
            for bom in (b"", BOM):
                original = bom + FIXTURE.replace(b"\n", newline)
                for statement, label in (
                    ("ВызватьИсключение;", "rethrow_ru"),
                    ("Raise;", "rethrow_en"),
                ):
                    with self.subTest(newline=newline, bom=bool(bom), label=label):
                        raw = candidate(original, statement, newline)
                        self.assertEqual(VERIFIER.repair_variant(raw, original), label)

    def test_other_edits_are_not_a_semantic_pass(self):
        valid = candidate(FIXTURE)
        invalid = {
            "unchanged": FIXTURE,
            "message": candidate(FIXTURE, 'Сообщить("Ошибка");'),
            "new_exception": candidate(FIXTURE, 'ВызватьИсключение "Ошибка";'),
            "extra_statement": candidate(FIXTURE, "ВызватьИсключение; Сообщить(1);"),
            "duplicate_rethrow": candidate(FIXTURE, "ВызватьИсключение; ВызватьИсключение;"),
            "changed_signature": valid.replace(
                "СохранитьДокумент(".encode(), "ДругаяПроцедура(".encode()
            ),
            "changed_write": valid.replace("Записать()".encode(), "Удалить()".encode()),
            "extra_comment": valid + b"// unrelated\n",
            "removed_comment": valid.split(b"\n", 1)[1],
            "changed_newlines": valid.replace(b"\n", b"\r\n"),
            "added_bom": BOM + valid,
        }
        for name, raw in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    VERIFIER.repair_variant(raw, FIXTURE)

    def test_existing_bom_and_crlf_cannot_be_removed_or_normalized(self):
        original = BOM + FIXTURE.replace(b"\n", b"\r\n")
        valid = candidate(original, newline=b"\r\n")
        for raw in (valid[3:], valid.replace(b"\r\n", b"\n")):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    VERIFIER.repair_variant(raw, original)

    def test_foreign_or_mixed_newline_baselines_are_rejected(self):
        originals = [
            FIXTURE.replace("СохранитьДокумент(".encode(), "ДругаяПроцедура(".encode()),
            FIXTURE.replace(b"\n", b"\r\n", 1),
            FIXTURE + b"// unrelated\n",
            FIXTURE.replace("    Исключение\n".encode(), b""),
        ]
        for original in originals:
            with self.subTest(original=original):
                with self.assertRaises(ValueError):
                    VERIFIER.repair_variant(candidate(original), original)

    def test_inputs_must_be_bytes(self):
        for raw, original in [
            (candidate(FIXTURE).decode(), FIXTURE),
            (candidate(FIXTURE), FIXTURE.decode()),
            (bytearray(candidate(FIXTURE)), FIXTURE),
            (None, FIXTURE),
        ]:
            with self.subTest(raw_type=type(raw), original_type=type(original)):
                with self.assertRaises(ValueError):
                    VERIFIER.repair_variant(raw, original)


if __name__ == "__main__":
    unittest.main()
