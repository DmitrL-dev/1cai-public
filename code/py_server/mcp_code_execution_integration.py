
"""
Интеграция Code Execution с существующим MCP Server

Добавляет новые MCP tools для code execution:
- execute_code: выполнить TypeScript код
- search_tools: semantic search по tools
- save_skill: сохранить skill
- load_skill: загрузить skill
"""

import logging
from typing import Any, Dict, List

from agent_orchestrator import get_orchestrator
from mcp_tools_search import get_search_service

logger = logging.getLogger(__name__)


def register_code_execution_tools(mcp_server):
    """
    Зарегистрировать Code Execution tools в MCP server
    
    Usage в вашем существующем mcp_server.py:
    
        from mcp_code_execution_integration import register_code_execution_tools
        
        # После создания server
        server = Server("1c-ai-stack")
        
        # Регистрируем code execution tools
        register_code_execution_tools(server)
    """
    
    orchestrator = get_orchestrator()
    search_service = get_search_service()
    
    # Tool 1: execute_code
    @mcp_server.tool()
    async def execute_code(
        code: str,
        agent_id: str = "user_agent",
        timeout: int = 30000
    ) -> Dict[str, Any]:
        """
        Выполнить TypeScript код в безопасном sandbox
        
        Args:
            code: TypeScript код для выполнения
            agent_id: ID агента (для logging)
            timeout: Timeout в миллисекундах
        
        Returns:
            Результат выполнения:
                - success: bool
                - output: str
                - errors: str
                - execution_time_ms: int
                - memory_used_mb: float
        
        Example:
            result = await execute_code(code='''
                import { getConfiguration } from './servers/1c/getConfiguration.ts';
                const config = await getConfiguration({ name: 'УТ' });
                console.log(config.name);
            ''')
        """
        
        result = await orchestrator.execution_service.execute_code(
            code=code,
            timeout=timeout,
            session_id=f"{agent_id}-{orchestrator._generate_task_id()}"
        )
        
        return {
            'success': result.success,
            'output': result.output,
            'errors': result.errors,
            'execution_time_ms': result.execution_time_ms,
            'memory_used_mb': result.memory_used_mb,
        }
    
    # Tool 2: execute_agent_task
    @mcp_server.tool()
    async def execute_agent_task(
        task: str,
        agent_id: str = "default_agent",
        save_skill: bool = False
    ) -> Dict[str, Any]:
        """
        Выполнить задачу через AI агента с code generation
        
        Полный workflow:
        1. Agent генерирует код
        2. Выполнение в sandbox
        3. PII protection
        4. (Опционально) сохранение skill
        
        Args:
            task: Описание задачи
            agent_id: ID агента
            save_skill: Сохранить как skill если успешно
        
        Returns:
            Результаты выполнения
        
        Example:
            result = await execute_agent_task(
                task="Получить метаданные конфигурации УТ",
                agent_id="architect_agent"
            )
        """
        
        return await orchestrator.execute_agent_task(
            task=task,
            agent_id=agent_id,
            save_skill=save_skill
        )
    
    # Tool 3: search_tools (progressive disclosure)
    @mcp_server.tool()
    async def search_tools(
        query: str,
        server: str = None,
        detail_level: str = "name_and_description",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search для MCP tools (Progressive Disclosure)
        
        Позволяет агентам находить нужные tools по смыслу запроса,
        вместо загрузки всех definitions upfront.
        
        Args:
            query: Поисковый запрос естественным языком
            server: Фильтр по server ("1c", "neo4j", etc.)
            detail_level: Уровень детализации
                - "name_only": только имя
                - "name_and_description": + описание
                - "full": полное определение с schemas
            limit: Максимум результатов (1-100)
        
        Returns:
            Список tools с relevance scores
        
        Examples:
            # Найти 1C tools для работы с метаданными
            tools = await search_tools(
                query="get 1C configuration metadata",
                server="1c",
                limit=5
            )
            
            # Найти graph database tools
            tools = await search_tools(
                query="store dependency graph",
                server="neo4j"
            )
        """
        
        return await search_service.search_tools(
            query=query,
            server=server,
            detail_level=detail_level,
            limit=limit
        )
    
    # Tool 4: get_tokenizer_stats
    @mcp_server.tool()
    async def get_tokenizer_stats() -> Dict[str, Any]:
        """
        Получить статистику PII токенизации
        
        Returns:
            Статистика:
                - total_tokens: количество токенизированных значений
                - tokens_by_type: распределение по типам (INN, NAME, etc.)
                - memory_usage_bytes: использование памяти
        """
        
        return orchestrator.tokenizer.get_stats()
    
    logger.info("✅ Registered Code Execution MCP tools:")
    logger.info("   - execute_code")
    logger.info("   - execute_agent_task")
    logger.info("   - search_tools")
    logger.info("   - get_tokenizer_stats")


# Example: Полная интеграция с MCP server
if __name__ == "__main__":
    """
    Пример как интегрировать в ваш существующий MCP server
    """
    
    print("""
Добавьте в ваш mcp_server.py:

```python
from mcp_code_execution_integration import register_code_execution_tools

# После создания server
server = Server("1c-ai-stack")

# ... ваши существующие tools ...

# Добавить code execution tools
register_code_execution_tools(server)

# Запустить server
```

Теперь у вас есть дополнительные tools:
1. execute_code - прямое выполнение TypeScript
2. execute_agent_task - full agent workflow
3. search_tools - progressive disclosure
4. get_tokenizer_stats - PII statistics
""")


