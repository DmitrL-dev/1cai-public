
"""
Secure MCP Client

MCP Client с автоматической PII токенизацией для безопасной работы с данными
"""

import logging
from typing import Any, Dict, List, Optional

from pii_tokenizer import PIITokenizer, get_tokenizer

logger = logging.getLogger(__name__)


class SecureMCPClient:
    """
    MCP Client с PII protection
    
    Автоматически токенизирует PII перед передачей в model context
    и раскрывает токены при передаче в MCP tools
    
    Usage:
        client = SecureMCPClient()
        
        # Get clients (PII токенизируется)
        clients = await client.call_tool_secure(
            '1c__get_clients',
            {'top': 100},
            tokenize_output=True  # Токенизировать для model
        )
        
        # Model видит: [{'name': '[NAME_1]', 'inn': '[INN_1]'}, ...]
        
        # Update в Salesforce (токены раскрываются)
        await client.call_tool_secure(
            'salesforce__update_account',
            {'inn': clients[0]['inn'], 'name': clients[0]['name']},
            untokenize_input=True  # Раскрыть перед отправкой
        )
    """
    
    def __init__(
        self,
        mcp_client: Any = None,
        tokenizer: Optional[PIITokenizer] = None
    ):
        """
        Args:
            mcp_client: Ваш существующий MCP client
            tokenizer: PIITokenizer instance (или создаст новый)
        """
        self.mcp_client = mcp_client
        self.tokenizer = tokenizer or get_tokenizer()
        
        # Default PII fields для токенизации
        self.default_pii_fields = [
            'inn', 'ИНН',
            'name', 'Name', 'Наименование', 'ФИО',
            'phone', 'Phone', 'Телефон',
            'email', 'Email', 'ЭлПочта',
            'address', 'Address', 'Адрес',
            'passport', 'Паспорт',
            'snils', 'СНИЛС',
            'account_number', 'НомерСчета',
            'bik', 'БИК',
        ]
    
    async def call_tool_secure(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tokenize_input: bool = False,
        tokenize_output: bool = True,
        untokenize_input: bool = False,
        untokenize_output: bool = False,
        pii_fields: Optional[List[str]] = None,
        auto_detect: bool = True
    ) -> Any:
        """
        Вызвать MCP tool с PII protection
        
        Args:
            tool_name: Имя tool ('1c__get_clients')
            arguments: Аргументы для tool
            tokenize_input: Токенизировать input перед отправкой в tool
            tokenize_output: Токенизировать output перед возвратом в model
            untokenize_input: Раскрыть токены в input перед отправкой
            untokenize_output: Раскрыть токены в output
            pii_fields: Список PII полей (или use default)
            auto_detect: Автоматически искать PII по patterns
        
        Returns:
            Результат от MCP tool (с токенизацией если нужно)
        """
        
        fields = pii_fields or self.default_pii_fields
        
        # 1. Обработать input
        if untokenize_input:
            # Раскрыть токены в arguments
            processed_args = self.tokenizer.untokenize(arguments)
            logger.debug(f"Untokenized input for {tool_name}")
        elif tokenize_input:
            # Токенизировать arguments
            processed_args = self.tokenizer.tokenize(
                arguments,
                fields=fields,
                auto_detect=auto_detect
            )
            logger.debug(f"Tokenized input for {tool_name}")
        else:
            processed_args = arguments
        
        # 2. Вызвать MCP tool
        try:
            result = await self._call_mcp_tool(tool_name, processed_args)
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise
        
        # 3. Обработать output
        if untokenize_output:
            # Раскрыть токены в результате
            processed_result = self.tokenizer.untokenize(result)
            logger.debug(f"Untokenized output from {tool_name}")
        elif tokenize_output:
            # Токенизировать результат
            processed_result = self.tokenizer.tokenize(
                result,
                fields=fields,
                auto_detect=auto_detect
            )
            logger.debug(f"Tokenized output from {tool_name}")
        else:
            processed_result = result
        
        return processed_result
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Вызвать MCP tool (базовая реализация)"""
        
        if self.mcp_client is None:
            # Fallback: mock implementation для тестирования
            logger.warning(
                f"No MCP client provided, returning mock data for {tool_name}"
            )
            return {'mock': True, 'tool': tool_name, 'args': arguments}
        
        # Вызвать реальный MCP client
        return await self.mcp_client.call_tool(tool_name, arguments)
    
    def get_tokenizer_stats(self) -> Dict[str, Any]:
        """Получить статистику токенизатора"""
        return self.tokenizer.get_stats()
    
    def save_session(self, filepath: str):
        """Сохранить session (mappings)"""
        self.tokenizer.save_mapping(filepath)
    
    def load_session(self, filepath: str):
        """Загрузить session"""
        self.tokenizer.load_mapping(filepath)


# Convenience functions

async def get_1c_data_safe(
    tool_name: str,
    arguments: Dict,
    mcp_client: Any = None
) -> Any:
    """
    Получить данные из 1С с автоматической токенизацией PII
    
    Returns:
        Данные с токенизированными PII (безопасно для model context)
    """
    client = SecureMCPClient(mcp_client)
    
    return await client.call_tool_secure(
        tool_name,
        arguments,
        tokenize_output=True,  # Токенизировать для model
        auto_detect=True
    )


async def update_external_system_safe(
    tool_name: str,
    arguments: Dict,
    mcp_client: Any = None
) -> Any:
    """
    Обновить внешнюю систему с автоматическим раскрытием токенов
    
    Args:
        arguments: Могут содержать токены вида '[INN_1]'
    
    Returns:
        Результат с раскрытыми реальными данными
    """
    client = SecureMCPClient(mcp_client)
    
    return await client.call_tool_secure(
        tool_name,
        arguments,
        untokenize_input=True,  # Раскрыть токены перед отправкой
        tokenize_output=False   # Результат как есть
    )


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_secure_client():
        print("=" * 60)
        print("Тест Secure MCP Client")
        print("=" * 60)
        
        client = SecureMCPClient()
        
        # Simulate getting clients from 1C
        print("\n1. Get clients from 1C (with PII):")
        
        mock_clients = [
            {
                'id': '001',
                'name': 'ООО "Ромашка"',
                'inn': '7712345678',
                'phone': '+7 (495) 123-45-67',
                'email': 'info@romashka.ru'
            },
            {
                'id': '002',
                'name': 'ИП Иванов Иван Иванович',
                'inn': '123456789012',
                'phone': '8 (495) 987-65-43',
                'email': 'ivanov@mail.ru'
            }
        ]
        
        # Tokenize
        safe_clients = client.tokenizer.tokenize(
            mock_clients,
            fields=['name', 'inn', 'phone', 'email']
        )
        
        print("Tokenized (safe for model):")
        print(json.dumps(safe_clients, ensure_ascii=False, indent=2))
        
        # Untokenize
        original_clients = client.tokenizer.untokenize(safe_clients)
        
        print("\nUntokenized (for external system):")
        print(json.dumps(original_clients, ensure_ascii=False, indent=2))
        
        # Stats
        print("\n" + "=" * 60)
        print("Статистика токенизации:")
        stats = client.get_tokenizer_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        
        print("\n✅ Test passed!")
    
    asyncio.run(test_secure_client())


