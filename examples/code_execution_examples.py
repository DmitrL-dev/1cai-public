
"""
Примеры использования Code Execution with MCP

Демонстрирует различные сценарии использования
"""

import asyncio
import sys
from pathlib import Path

# Add code directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'code' / 'py_server'))

from agent_orchestrator import execute_agent_task
from execution_service import CodeExecutionService

from pii_tokenizer import PIITokenizer


async def example_1_simple_execution():
    """
    Пример 1: Простое выполнение кода
    """
    print("\n" + "=" * 60)
    print("Пример 1: Простое выполнение TypeScript кода")
    print("=" * 60)
    
    service = CodeExecutionService()
    
    code = '''
console.log("Hello from Code Execution!");

// Simple calculation
const numbers = [1, 2, 3, 4, 5];
const sum = numbers.reduce((a, b) => a + b, 0);
const avg = sum / numbers.length;

console.log(`Numbers: ${numbers.join(', ')}`);
console.log(`Sum: ${sum}`);
console.log(`Average: ${avg}`);
'''
    
    try:
        result = await service.execute_code(code)
        
        print(f"\n✅ Execution successful!")
        print(f"Output:\n{result.output}")
        print(f"Time: {result.execution_time_ms}ms")
        print(f"Memory: {result.memory_used_mb}MB")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("⚠️  Make sure Execution Server is running:")
        print("   cd execution-env")
        print("   deno run --allow-all execution-harness.ts")


async def example_2_mcp_tool_call():
    """
    Пример 2: Вызов MCP tools из кода
    """
    print("\n" + "=" * 60)
    print("Пример 2: Вызов MCP Tools")
    print("=" * 60)
    
    service = CodeExecutionService()
    
    code = '''
// Import generated API
import { getConfiguration } from './servers/1c/getConfiguration.ts';

// Call MCP tool
const config = await getConfiguration({
  name: 'УТ',
  includeMetadata: false
});

console.log("Configuration loaded:");
console.log(JSON.stringify(config, null, 2));
'''
    
    print("Code to execute:")
    print(code)
    
    try:
        result = await service.execute_code(code, timeout=10000)
        
        if result.success:
            print(f"\n✅ Success!")
            print(f"Output:\n{result.output}")
        else:
            print(f"\n⚠️  Execution failed (expected if MCP server not running)")
            print(f"Errors:\n{result.errors}")
    except Exception as e:
        print(f"\n⚠️  Error: {e}")


async def example_3_pii_protection():
    """
    Пример 3: PII Protection (152-ФЗ)
    """
    print("\n" + "=" * 60)
    print("Пример 3: PII Protection (152-ФЗ)")
    print("=" * 60)
    
    tokenizer = PIITokenizer()
    
    # Simulate client data from 1C
    clients = [
        {
            'id': '001',
            'name': 'ООО "Ромашка"',
            'inn': '7712345678',
            'phone': '+7 (495) 123-45-67',
            'email': 'info@romashka.ru',
            'amount': 150000.00
        },
        {
            'id': '002',
            'name': 'ИП Иванов Иван Иванович',
            'inn': '123456789012',
            'phone': '8 (926) 987-65-43',
            'email': 'ivanov@mail.ru',
            'amount': 75000.00
        }
    ]
    
    print("\n📊 Original data (confidential):")
    print(json.dumps(clients, ensure_ascii=False, indent=2))
    
    # Tokenize PII
    tokenized = tokenizer.tokenize(
        clients,
        fields=['name', 'inn', 'phone', 'email']
    )
    
    print("\n🔒 Tokenized data (safe for AI model):")
    print(json.dumps(tokenized, ensure_ascii=False, indent=2))
    
    # Model видит только токены!
    # Но данные можно untokenize для передачи в другие системы
    
    untokenized = tokenizer.untokenize(tokenized)
    
    print("\n🔓 Untokenized (for external system transfer):")
    print(json.dumps(untokenized, ensure_ascii=False, indent=2))
    
    # Verify
    assert untokenized == clients
    print("\n✅ PII Protection works correctly!")
    
    # Stats
    stats = tokenizer.get_stats()
    print(f"\n📊 Tokenization stats:")
    print(f"   Total tokens: {stats['total_tokens']}")
    print(f"   By type: {stats['tokens_by_type']}")


async def example_4_agent_task():
    """
    Пример 4: Полный Agent Task Workflow
    """
    print("\n" + "=" * 60)
    print("Пример 4: Agent Task Workflow")
    print("=" * 60)
    
    task = "Получить конфигурацию УТ и вывести основную информацию"
    agent_id = "architect_agent"
    
    print(f"\n📋 Task: {task}")
    print(f"🤖 Agent: {agent_id}")
    
    try:
        result = await execute_agent_task(
            task=task,
            agent_id=agent_id
        )
        
        print(f"\n✅ Task completed!")
        print(f"Task ID: {result.get('task_id', 'N/A')}")
        print(f"Success: {result['success']}")
        
        if result['success']:
            print(f"\nOutput:\n{result['output']}")
            print(f"\nMetrics:")
            print(f"  Execution time: {result['execution_time_ms']}ms")
            print(f"  Memory used: {result['memory_used_mb']}MB")
            
            if result.get('skill_id'):
                print(f"  Skill saved: {result['skill_id']}")
        else:
            print(f"\nError: {result.get('error', 'Unknown')}")
    
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        print("   Make sure services are running")


async def example_5_progressive_disclosure():
    """
    Пример 5: Progressive Disclosure (search_tools)
    """
    print("\n" + "=" * 60)
    print("Пример 5: Progressive Disclosure")
    print("=" * 60)
    
    service = CodeExecutionService()
    
    code = '''
// Import search function
import { searchTools } from './client.ts';

// Agent ищет нужные tools вместо загрузки всех
const tools = await searchTools({
  query: "get 1C configuration metadata",
  server: "1c",
  detailLevel: "name_and_description",
  limit: 5
});

console.log(`Found ${tools.length} relevant tools:`);

for (const tool of tools) {
  console.log(`  - ${tool.name} (score: ${tool.score.toFixed(2)})`);
  console.log(`    ${tool.description}`);
}

// Теперь загружаем только нужный tool
if (tools.length > 0) {
  const topTool = tools[0];
  console.log(`\\nUsing top tool: ${topTool.name}`);
}
'''
    
    print("Code demonstrating progressive disclosure:")
    print(code)
    
    try:
        result = await service.execute_code(code, timeout=10000)
        
        if result.success:
            print(f"\n✅ Success!")
            print(f"Output:\n{result.output}")
        else:
            print(f"\n⚠️  Expected (search_tools requires Qdrant indexing)")
            print(f"Errors:\n{result.errors}")
    except Exception as e:
        print(f"\n⚠️  Error: {e}")


async def example_6_data_pipeline():
    """
    Пример 6: Complex Data Pipeline
    """
    print("\n" + "=" * 60)
    print("Пример 6: Complex Data Pipeline")
    print("=" * 60)
    
    service = CodeExecutionService()
    
    code = '''
// Simulate complex data pipeline

// Step 1: Get data from 1C (simulated)
const mockData = [
  { id: 1, type: 'Catalog', name: 'Номенклатура', tableCount: 5 },
  { id: 2, type: 'Document', name: 'ПродажаТоваров', tableCount: 12 },
  { id: 3, type: 'Catalog', name: 'Контрагенты', tableCount: 3 },
];

console.log(`Step 1: Got ${mockData.length} metadata objects`);

// Step 2: Filter in execution environment (NOT in model context!)
const catalogs = mockData.filter(item => item.type === 'Catalog');

console.log(`Step 2: Filtered to ${catalogs.length} catalogs`);

// Step 3: Transform
const summary = catalogs.map(c => ({
  name: c.name,
  complexity: c.tableCount > 5 ? 'high' : 'low'
}));

console.log(`Step 3: Transformed data`);

// Step 4: Save to workspace
await Deno.writeTextFile(
  './workspace/catalogs-summary.json',
  JSON.stringify(summary, null, 2)
);

console.log(`Step 4: Saved to workspace/catalogs-summary.json`);

// Only summary goes to model context
console.log(`\\nFinal summary: ${summary.length} catalogs processed`);
'''
    
    try:
        result = await service.execute_code(code, save_output=True)
        
        if result.success:
            print(f"\n✅ Pipeline executed successfully!")
            print(f"Output:\n{result.output}")
            
            # Check if file was created
            workspace_file = Path('../execution-env/workspace/catalogs-summary.json')
            if workspace_file.exists():
                print(f"\n📁 File created: {workspace_file}")
                print(f"Content:\n{workspace_file.read_text()}")
        else:
            print(f"\n❌ Pipeline failed")
            print(f"Errors:\n{result.errors}")
    except Exception as e:
        print(f"\n⚠️  Error: {e}")


async def run_all_examples():
    """Запустить все примеры"""
    print("🚀 Code Execution Examples")
    print("=" * 60)
    print()
    
    # Note about requirements
    print("📋 Requirements:")
    print("   1. Deno installed (deno --version)")
    print("   2. Execution server running (cd execution-env; deno run --allow-all execution-harness.ts)")
    print("   3. (Optional) MCP server for full tests")
    print()
    input("Press Enter to continue...")
    
    # Run examples
    await example_1_simple_execution()
    
    await example_2_mcp_tool_call()
    
    await example_3_pii_protection()
    
    await example_4_agent_task()
    
    await example_5_progressive_disclosure()
    
    await example_6_data_pipeline()
    
    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_examples())


