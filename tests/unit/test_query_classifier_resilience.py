"""
Unit tests for QueryClassifier resilience
"""

from src.ai.query_classifier import QueryClassifier, QueryIntent, QueryType


class TestQueryClassifierResilience:
    """Test robustness of QueryClassifier"""

    def test_initialization(self):
        """Test initialization logic"""
        classifier = QueryClassifier()
        assert classifier is not None

    def test_classify_empty_input(self):
        """Test classification with empty or None input"""
        classifier = QueryClassifier()

        # None input (should be handled safely due to our refactor)
        intent = classifier.classify(None)
        assert intent.query_type == QueryType.UNKNOWN
        assert intent.confidence == 0.0

        # Empty string
        intent = classifier.classify("")
        assert intent.query_type == QueryType.UNKNOWN

    def test_classify_long_input(self):
        """Test classification with extremely long input (ReDoS protection)"""
        classifier = QueryClassifier()

        # Create a massive string
        long_query = "test " * 5000

        # Should not hang or crash
        intent = classifier.classify(long_query)
        assert isinstance(intent, QueryIntent)

    def test_classify_standard_1c(self):
        """Test standard 1C query classification"""
        classifier = QueryClassifier()

        query = "Как реализовано проведение документа в УТ?"
        intent = classifier.classify(query)

        assert intent.query_type == QueryType.STANDARD_1C
        assert intent.confidence > 0.0

    def test_classify_graph_query(self):
        """Test graph query classification"""
        classifier = QueryClassifier()

        query = "Где используется справочник Номенклатура?"
        intent = classifier.classify(query)

        assert intent.query_type == QueryType.GRAPH_QUERY
        assert intent.confidence > 0.0

    def test_tool_suggestion_resilience(self):
        """Test that tool suggestions don't crash on import errors"""
        # This test assumes imports might fail or succeed depending on env
        # We just want to ensure classify() doesn't raise
        classifier = QueryClassifier()
        intent = classifier.classify("optimze this code")
        assert isinstance(intent.suggested_tools, list)
