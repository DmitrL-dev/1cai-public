
"""
MCP Tool: search_tools

Semantic search для MCP tools (progressive disclosure)
"""

import logging
from typing import Any, Dict, List, Optional

from tool_indexer import ToolIndexer

logger = logging.getLogger(__name__)


class SearchToolsService:
    """
    Сервис поиска MCP tools
    
    Интегрируется с MCP server как tool
    """
    
    def __init__(self, indexer: Optional[ToolIndexer] = None):
        self.indexer = indexer or ToolIndexer()
    
    async def search_tools(
        self,
        query: str,
        server: Optional[str] = None,
        detail_level: str = "name_and_description",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search для MCP tools
        
        Args:
            query: Поисковый запрос (естественный язык)
            server: Фильтр по server (опционально)
            detail_level: Уровень детализации результатов
                - "name_only": только имя и server
                - "name_and_description": + описание
                - "full": полное определение tool с schemas
            limit: Максимум результатов
        
        Returns:
            Список найденных tools с relevance scores
        
        Examples:
            # Найти tools для работы с метаданными 1С
            results = await search_tools(
                query="get 1C configuration metadata",
                server="1c",
                limit=5
            )
            
            # Найти tools для работы с графами
            results = await search_tools(
                query="graph database query",
                detail_level="full"
            )
        """
        
        # Валидация
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if detail_level not in ["name_only", "name_and_description", "full"]:
            raise ValueError(
                f"Invalid detail_level: {detail_level}. "
                "Must be: name_only, name_and_description, or full"
            )
        
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")
        
        # Search
        results = await self.indexer.search_tools(
            query=query,
            server=server,
            detail_level=detail_level,
            limit=limit
        )
        
        logger.info(
            f"search_tools: query='{query}', server={server}, "
            f"found {len(results)} results"
        )
        
        return results


# Singleton instance
_search_service: Optional[SearchToolsService] = None


def get_search_service() -> SearchToolsService:
    """Получить singleton instance"""
    global _search_service
    
    if _search_service is None:
        _search_service = SearchToolsService()
    
    return _search_service


async def search_tools(
    query: str,
    server: Optional[str] = None,
    detail_level: str = "name_and_description",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Convenience function для search_tools
    
    Usage:
        from mcp_tools_search import search_tools
        
        results = await search_tools(
            query="get 1C metadata",
            server="1c"
        )
    """
    service = get_search_service()
    return await service.search_tools(query, server, detail_level, limit)


# Для интеграции с MCP Server
def register_search_tools_mcp_tool(mcp_server):
    """
    Зарегистрировать search_tools как MCP tool
    
    Usage в вашем mcp_server.py:
        from mcp_tools_search import register_search_tools_mcp_tool
        
        register_search_tools_mcp_tool(server)
    """
    
    @mcp_server.tool()
    async def search_tools_mcp(
        query: str,
        server: str = None,
        detail_level: str = "name_and_description",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search для MCP tools (progressive disclosure)
        
        Позволяет агентам находить нужные tools по смыслу запроса,
        вместо загрузки всех tool definitions upfront.
        
        Args:
            query: Поисковый запрос ("get 1C configuration", "database query", etc.)
            server: Фильтр по server ("1c", "neo4j", "qdrant", etc.)
            detail_level: "name_only" | "name_and_description" | "full"
            limit: Максимум результатов (default: 10)
        
        Returns:
            Список найденных tools с relevance scores
        
        Examples:
            # Find 1C metadata tools
            results = search_tools(
                query="get 1C configuration metadata",
                server="1c",
                limit=5
            )
            
            # Find graph database tools
            results = search_tools(
                query="store dependency graph",
                server="neo4j"
            )
        """
        return await search_tools(query, server, detail_level, limit)
    
    logger.info("✅ Registered search_tools MCP tool")


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_search():
        print("=" * 60)
        print("Тест search_tools")
        print("=" * 60)
        
        # Mock data для теста
        tools = [
            {
                'name': 'get_configuration',
                'server': '1c',
                'description': 'Получить метаданные конфигурации 1С',
                'inputSchema': {'properties': {'name': {'type': 'string'}}}
            },
            {
                'name': 'get_metadata',
                'server': '1c',
                'description': 'Получить метаданные объекта 1С',
                'inputSchema': {'properties': {'objectType': {'type': 'string'}}}
            },
            {
                'name': 'run_cypher',
                'server': 'neo4j',
                'description': 'Выполнить Cypher запрос в Neo4j граф базе',
                'inputSchema': {'properties': {'query': {'type': 'string'}}}
            }
        ]
        
        try:
            # Index
            service = get_search_service()
            await service.indexer.index_tools(tools)
            
            # Search
            print("\n🔍 Searching for: '1C configuration'")
            results = await search_tools(
                query="1C configuration",
                detail_level="name_and_description"
            )
            
            for i, tool in enumerate(results, 1):
                print(f"{i}. {tool['name']} (score: {tool['score']:.3f})")
                print(f"   {tool['description']}")
            
            print("\n✅ Test passed!")
            
        except Exception as e:
            print(f"\n⚠️  Test skipped: {e}")
            print("   Ensure Qdrant is running and dependencies installed")
    
    asyncio.run(test_search())


