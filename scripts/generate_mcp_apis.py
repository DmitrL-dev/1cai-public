
"""
Скрипт для генерации TypeScript APIs из MCP tools

Usage:
    python scripts/generate_mcp_apis.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir / 'code' / 'py_server'))

from mcp_code_generator import generate_all_servers


async def get_mock_tools():
    """
    Mock tools для тестирования генератора
    
    TODO: Заменить на реальные tools из вашего MCP server
    """
    
    tools_1c = [
        {
            'name': 'get_configuration',
            'description': 'Получить метаданные конфигурации 1С',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Имя конфигурации (УТ, Б УХ, ERP и т.д.)'
                    },
                    'includeMetadata': {
                        'type': 'boolean',
                        'description': 'Включить полные метаданные'
                    }
                },
                'required': ['name']
            }
        },
        {
            'name': 'execute_query',
            'description': 'Выполнить SQL запрос в базе 1С',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'SQL запрос'
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Лимит результатов'
                    }
                },
                'required': ['query']
            }
        },
        {
            'name': 'get_metadata',
            'description': 'Получить метаданные объекта 1С',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'objectType': {
                        'type': 'string',
                        'description': 'Тип объекта (Catalog, Document, Report и т.д.)'
                    },
                    'objectName': {
                        'type': 'string',
                        'description': 'Имя объекта'
                    }
                },
                'required': ['objectType', 'objectName']
            }
        }
    ]
    
    tools_neo4j = [
        {
            'name': 'run_cypher',
            'description': 'Выполнить Cypher запрос в Neo4j',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Cypher query'
                    },
                    'parameters': {
                        'type': 'object',
                        'description': 'Query parameters'
                    }
                },
                'required': ['query']
            }
        },
        {
            'name': 'store_graph',
            'description': 'Сохранить граф в Neo4j',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'nodes': {
                        'type': 'array',
                        'description': 'Graph nodes'
                    },
                    'relationships': {
                        'type': 'array',
                        'description': 'Graph relationships'
                    }
                },
                'required': ['nodes', 'relationships']
            }
        }
    ]
    
    tools_qdrant = [
        {
            'name': 'search',
            'description': 'Семантический поиск в Qdrant',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'collection': {
                        'type': 'string',
                        'description': 'Collection name'
                    },
                    'query': {
                        'type': 'string',
                        'description': 'Search query'
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Result limit'
                    }
                },
                'required': ['collection', 'query']
            }
        },
        {
            'name': 'insert',
            'description': 'Вставить vectors в Qdrant',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'collection': {
                        'type': 'string',
                        'description': 'Collection name'
                    },
                    'points': {
                        'type': 'array',
                        'description': 'Points to insert'
                    }
                },
                'required': ['collection', 'points']
            }
        }
    ]
    
    return {
        '1c': tools_1c,
        'neo4j': tools_neo4j,
        'qdrant': tools_qdrant,
    }


async def main():
    print("🚀 MCP API Generator")
    print("=" * 60)
    print()
    
    # Get tools
    print("📦 Loading MCP tools...")
    tools = await get_mock_tools()
    
    total = sum(len(t) for t in tools.values())
    print(f"  Found {total} tools across {len(tools)} servers")
    print()
    
    # Generate
    print("🔨 Generating TypeScript APIs...")
    output_dir = "./execution-env/servers"
    generated_count = generate_all_servers(tools, output_dir)
    
    print()
    print("=" * 60)
    print(f"✅ Success! Generated {generated_count} tools")
    print()
    print("📁 Check output:")
    print(f"   {output_dir}/")
    print()
    print("Next steps:")
    print("  1. Start execution server:")
    print("     cd execution-env")
    print("     deno run --allow-all execution-harness.ts")
    print()
    print("  2. Test from Python:")
    print("     python code/py_server/execution_service.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())

