"""ANTLR4-based BSL parser for accurate function/procedure extraction.

Uses ANTLR4 grammar from 1c-syntax/bsl-parser for precise AST parsing.
Replaces regex-based function boundary detection in OneCCodeGraphBuilder.

Architecture (hybrid):
    ANTLR4 → accurate function/procedure boundaries (name, line, export, type)
    Regex  → call extraction, query extraction, complexity (within function bodies)

This hybrid approach gives us:
    - Accurate boundaries even with nested preprocessor directives, strings
      containing keywords, and other edge cases regex can't handle
    - Zero regression risk on call/query/complexity extraction (same regex)
    - Incremental path to full AST analysis (replace regex piece by piece)
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Add generated parser directory to sys.path for ANTLR4 imports
_generated_dir = str(Path(__file__).parent / "generated")
if _generated_dir not in sys.path:
    sys.path.insert(0, _generated_dir)

try:
    from antlr4 import CommonTokenStream, InputStream  # type: ignore[import-untyped]
    from BSLLexer import BSLLexer  # type: ignore[import-not-found]
    from BSLParser import BSLParser  # type: ignore[import-not-found]
    from BSLParserVisitor import BSLParserVisitor  # type: ignore[import-not-found]

    ANTLR4_AVAILABLE = True
except ImportError as _exc:
    ANTLR4_AVAILABLE = False
    BSLParserVisitor = object  # type: ignore[assignment,misc]
    logger.warning(
        "ANTLR4 runtime not available: %s — falling back to regex parser", _exc
    )


@dataclass
class BslSubroutine:
    """Extracted function/procedure boundary info from AST."""

    name: str
    line: int
    end_line: int
    is_export: bool
    is_function: bool  # True = function, False = procedure
    body_text: str  # raw body text for regex-based call/query/complexity analysis


class _SilentErrorListener:
    """Suppresses ANTLR4 error output to stderr."""

    def syntaxError(self, *args, **kwargs):  # noqa: N802
        pass

    def reportAmbiguity(self, *args, **kwargs):  # noqa: N802
        pass

    def reportAttemptingFullContext(self, *args, **kwargs):  # noqa: N802
        pass

    def reportContextSensitivity(self, *args, **kwargs):  # noqa: N802
        pass


class BslAstVisitor(BSLParserVisitor):  # type: ignore[misc]
    """Walks BSL AST to extract function/procedure boundaries.

    Only extracts structural info (boundaries, names, export flags).
    Call/query/complexity analysis is done by regex on the extracted body text,
    keeping backward compatibility with OneCCodeGraphBuilder.
    """

    def __init__(self, source_text: str):
        self.source_text = source_text
        self.subroutines: list[BslSubroutine] = []

    # --- AST traversal ---

    def visitFile(self, ctx: "BSLParser.FileContext"):
        return self.visitChildren(ctx)

    def visitSubs(self, ctx: "BSLParser.SubsContext"):
        return self.visitChildren(ctx)

    def visitSub(self, ctx: "BSLParser.SubContext"):
        return self.visitChildren(ctx)

    def visitProcedure(self, ctx: "BSLParser.ProcedureContext"):
        self._extract_sub(ctx, is_function=False)
        return None  # boundaries extracted, no deeper walk needed

    def visitFunction(self, ctx: "BSLParser.FunctionContext"):
        self._extract_sub(ctx, is_function=True)
        return None

    def _extract_sub(self, ctx, is_function: bool) -> None:
        """Extract a single function/procedure from AST context."""
        try:
            decl = ctx.funcDeclaration() if is_function else ctx.procDeclaration()
            name = decl.subName().getText()
            is_export = decl.EXPORT_KEYWORD() is not None
            line = ctx.start.line
            end_line = ctx.stop.line

            # Extract body text from subCodeBlock
            code_block = ctx.subCodeBlock()
            if code_block and code_block.start and code_block.stop:
                body_start = code_block.start.start
                body_stop = code_block.stop.stop + 1
                body_text = self.source_text[body_start:body_stop]
            else:
                body_text = ""

            self.subroutines.append(
                BslSubroutine(
                    name=name,
                    line=line,
                    end_line=end_line,
                    is_export=is_export,
                    is_function=is_function,
                    body_text=body_text,
                )
            )
        except Exception as e:
            logger.warning("Failed to extract subroutine from AST: %s", e)


def parse_bsl_source(source: str) -> list[BslSubroutine] | None:
    """Parse BSL source code using ANTLR4 and return extracted subroutines.

    Returns:
        list[BslSubroutine] on success (may be empty for module-level code).
        None if ANTLR4 is not available (caller should fall back to regex).
    """
    if not ANTLR4_AVAILABLE:
        return None

    try:
        input_stream = InputStream(source)
        lexer = BSLLexer(input_stream)
        lexer.removeErrorListeners()
        lexer.addErrorListener(_SilentErrorListener())

        token_stream = CommonTokenStream(lexer)

        parser = BSLParser(token_stream)
        parser.removeErrorListeners()
        parser.addErrorListener(_SilentErrorListener())

        tree = parser.file_()

        visitor = BslAstVisitor(source)
        visitor.visit(tree)

        logger.debug(
            "ANTLR4 parsed %d subroutines (errors: %d)",
            len(visitor.subroutines),
            parser.getNumberOfSyntaxErrors(),
        )
        return visitor.subroutines

    except Exception as e:
        logger.warning("ANTLR4 parse failed, will fall back to regex: %s", e)
        return None
