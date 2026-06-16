# -*- coding: utf-8 -*-
"""Unit tests for ANTLR4 BSL parser integration."""

import os
import tempfile
from pathlib import Path

import pytest


class TestAntlr4BslParser:
    """Tests for src/parser/bsl_ast_visitor.py — ANTLR4-based BSL parsing."""

    def test_antlr4_available(self):
        from src.parser.bsl_ast_visitor import ANTLR4_AVAILABLE

        assert ANTLR4_AVAILABLE is True

    def test_parse_empty_source(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        result = parse_bsl_source("")
        assert result is not None
        assert len(result) == 0

    def test_parse_single_function(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = self._read_fixture("sample_antlr4.bsl")
        result = parse_bsl_source(source)
        assert result is not None
        assert len(result) == 2

    def test_function_properties(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = self._read_fixture("sample_antlr4.bsl")
        result = parse_bsl_source(source)
        func = next(s for s in result if s.is_function)
        assert func.is_export is True
        assert func.line == 1
        assert func.is_function is True

    def test_procedure_properties(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = self._read_fixture("sample_antlr4.bsl")
        result = parse_bsl_source(source)
        proc = next(s for s in result if not s.is_function)
        assert proc.is_export is False
        assert proc.line == 5
        assert proc.is_function is False

    def test_body_text_extraction(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = self._read_fixture("sample_antlr4.bsl")
        result = parse_bsl_source(source)
        proc = next(s for s in result if not s.is_function)
        assert len(proc.body_text) > 0

    def test_parse_english_keywords(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = "Function MyTest() Export\n    Return 1;\nEndFunction\n"
        result = parse_bsl_source(source)
        assert result is not None
        assert len(result) == 1
        assert result[0].is_function is True
        assert result[0].is_export is True

    def test_parse_mixed_bilingual(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = self._read_fixture("sample_antlr4.bsl")
        eng_source = "Function EngFunc()\n    Return 42;\nEndFunction\n"
        combined = source + "\n" + eng_source
        result = parse_bsl_source(combined)
        assert result is not None
        assert len(result) == 3

    def test_parse_no_export(self):
        from src.parser.bsl_ast_visitor import parse_bsl_source

        source = "Procedure Internal()\n    // nothing\nEndProcedure\n"
        result = parse_bsl_source(source)
        assert result is not None
        assert len(result) == 1
        assert result[0].is_export is False

    def test_builder_antlr4_integration(self):
        """Verify OneCCodeGraphBuilder uses ANTLR4 parser."""
        from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            bsl_path = Path(tmpdir) / "TestModule.bsl"
            source = self._read_fixture("sample_antlr4.bsl")
            bsl_path.write_text(source, encoding="utf-8")

            builder = OneCCodeGraphBuilder(config_path=tmpdir)
            builder._parse_bsl_file(bsl_path, "TestModule")

            assert len(builder.functions) == 2
            func_names = {f.name for f in builder.functions}
            assert len(func_names) == 2

    def test_builder_fallback_consistency(self):
        """ANTLR4 and regex produce same function count."""
        from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder

        source = self._read_fixture("sample_antlr4.bsl")

        with tempfile.TemporaryDirectory() as tmpdir:
            bsl_path = Path(tmpdir) / "Module.bsl"
            bsl_path.write_text(source, encoding="utf-8")

            # ANTLR4 path
            b1 = OneCCodeGraphBuilder(config_path=tmpdir)
            b1._parse_bsl_file(bsl_path, "M")
            antlr_count = len(b1.functions)

            # Regex path
            b2 = OneCCodeGraphBuilder(config_path=tmpdir)
            b2._parse_bsl_file_regex(source, "M")
            regex_count = len(b2.functions)

            assert antlr_count == regex_count == 2

    @staticmethod
    def _read_fixture(name: str) -> str:
        fixture_path = Path(__file__).parent.parent / "fixtures" / name
        return fixture_path.read_text(encoding="utf-8")
