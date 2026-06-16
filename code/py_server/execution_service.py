
"""
Code Execution Service

Интеграция Python backend с Deno Execution Harness
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Результат выполнения кода"""
    
    def __init__(self, data: Dict[str, Any]):
        self.success = data.get('success', False)
        self.output = data.get('output', '')
        self.errors = data.get('errors', '')
        self.execution_time_ms = data.get('executionTimeMs', 0)
        self.memory_used_mb = data.get('memoryUsedMB', 0)
        self.exit_code = data.get('exitCode', 1)
    
    def __repr__(self):
        return f"ExecutionResult(success={self.success}, time={self.execution_time_ms}ms)"


class CodeExecutionService:
    """
    Сервис для выполнения AI-generated кода через Deno harness
    """
    
    def __init__(
        self, 
        harness_url: str = "http://localhost:8001",
        timeout: int = 60
    ):
        self.harness_url = harness_url
        self.default_timeout = timeout
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    
    async def execute_code(
        self,
        code: str,
        timeout: Optional[int] = None,
        session_id: Optional[str] = None,
        save_output: bool = False
    ) -> ExecutionResult:
        """
        Выполнить TypeScript код через Deno harness
        
        Args:
            code: TypeScript код для выполнения
            timeout: Timeout в миллисекундах (default: 30000)
            session_id: ID сессии для группировки executions
            save_output: Сохранить output в workspace
        
        Returns:
            ExecutionResult с результатами
        """
        
        payload = {
            "code": code,
            "timeout": timeout or 30000,
            "sessionId": session_id,
            "saveOutput": save_output
        }
        
        try:
            response = await self.client.post(
                f"{self.harness_url}/",
                json=payload
            )
            response.raise_for_status()
            
            result_data = response.json()
            return ExecutionResult(result_data)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during code execution: {e}")
            return ExecutionResult({
                'success': False,
                'errors': f"HTTP {e.response.status_code}: {e.response.text}"
            })
        except httpx.RequestError as e:
            logger.error(f"Request error during code execution: {e}")
            return ExecutionResult({
                'success': False,
                'errors': f"Connection error: {str(e)}"
            })
        except Exception as e:
            logger.error(f"Unexpected error during code execution: {e}")
            return ExecutionResult({
                'success': False,
                'errors': f"Unexpected error: {str(e)}"
            })
    
    async def execute_with_monitoring(
        self,
        code: str,
        agent_id: str,
        task_id: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Выполнить код с мониторингом и логированием
        
        Args:
            code: TypeScript код
            agent_id: ID агента (для логирования)
            task_id: ID задачи
            timeout: Timeout
        
        Returns:
            ExecutionResult
        """
        
        # Log start
        await self._log_execution_start(agent_id, task_id, code)
        
        # Execute
        result = await self.execute_code(
            code=code,
            timeout=timeout,
            session_id=f"{agent_id}-{task_id}",
            save_output=True
        )
        
        # Log result
        await self._log_execution_result(agent_id, task_id, result)
        
        # Store metrics
        await self._store_metrics(agent_id, result)
        
        return result
    
    async def _log_execution_start(
        self, 
        agent_id: str, 
        task_id: str, 
        code: str
    ):
        """Логировать начало выполнения"""
        logger.info(
            f"Execution started - Agent: {agent_id}, Task: {task_id}, "
            f"Code length: {len(code)} chars"
        )
        
        # TODO: Сохранить в PostgreSQL или ELK
        # await self.db.log_execution_start(...)
    
    async def _log_execution_result(
        self,
        agent_id: str,
        task_id: str,
        result: ExecutionResult
    ):
        """Логировать результат выполнения"""
        logger.info(
            f"Execution completed - Agent: {agent_id}, Task: {task_id}, "
            f"Success: {result.success}, Time: {result.execution_time_ms}ms, "
            f"Memory: {result.memory_used_mb}MB"
        )
        
        if not result.success:
            logger.error(f"Execution errors: {result.errors}")
        
        # TODO: Сохранить в PostgreSQL
    
    async def _store_metrics(
        self,
        agent_id: str,
        result: ExecutionResult
    ):
        """Сохранить метрики в Prometheus"""
        # TODO: Push метрики в Prometheus
        # Metrics:
        # - code_execution_duration_ms
        # - code_execution_memory_mb
        # - code_execution_success_rate
        # - code_execution_total
    
    async def health_check(self) -> bool:
        """Проверить доступность Execution Harness"""
        try:
            # Простой test execution
            test_code = 'console.log("health check");'
            result = await self.execute_code(test_code, timeout=5000)
            return result.success
        except:
            return False
    
    async def close(self):
        """Закрыть HTTP client"""
        await self.client.aclose()


# Singleton instance
_execution_service: Optional[CodeExecutionService] = None


def get_execution_service() -> CodeExecutionService:
    """Получить singleton instance ExecutionService"""
    global _execution_service
    
    if _execution_service is None:
        _execution_service = CodeExecutionService()
    
    return _execution_service


async def execute_agent_code(
    code: str,
    agent_id: str = "unknown",
    task_id: str = "unknown",
    timeout: Optional[int] = None
) -> ExecutionResult:
    """
    Convenience function для выполнения кода агента
    
    Usage:
        result = await execute_agent_code(
            code='const x = 1 + 1; console.log(x);',
            agent_id='architect_agent',
            task_id='task_123'
        )
    """
    service = get_execution_service()
    return await service.execute_with_monitoring(
        code=code,
        agent_id=agent_id,
        task_id=task_id,
        timeout=timeout
    )


# Example usage
if __name__ == "__main__":
    async def main():
        service = CodeExecutionService()
        
        # Test simple execution
        test_code = """
console.log("Hello from Deno!");
const result = 1 + 1;
console.log(`Result: ${result}`);
"""
        
        print("Testing code execution...")
        result = await service.execute_code(test_code)
        
        print(f"Success: {result.success}")
        print(f"Output: {result.output}")
        print(f"Errors: {result.errors}")
        print(f"Execution time: {result.execution_time_ms}ms")
        print(f"Memory used: {result.memory_used_mb}MB")
        
        await service.close()
    
    asyncio.run(main())


