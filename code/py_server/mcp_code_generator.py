
"""
MCP Code Generator

Генерирует TypeScript API из MCP tool definitions
для использования в Code Execution Environment
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MCPCodeGenerator:
    """Генератор TypeScript API из MCP tools"""
    
    def __init__(self, output_dir: str = "./execution-env/servers"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_from_mcp_server(
        self,
        server_name: str,
        tools: List[Dict[str, Any]]
    ):
        """
        Генерировать TypeScript API для MCP server
        
        Args:
            server_name: Имя сервера ("1c", "neo4j", "qdrant", etc.)
            tools: Список tool definitions
        """
        
        logger.info(f"Generating TypeScript API for server '{server_name}'...")
        
        server_dir = self.output_dir / server_name
        server_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate index.ts (экспортирует все tools)
        self._generate_index(server_dir, tools, server_name)
        
        # Generate individual tool files
        for tool in tools:
            self._generate_tool_file(server_dir, tool, server_name)
        
        logger.info(
            f"✅ Generated {len(tools)} tools for server '{server_name}' "
            f"in {server_dir}"
        )
    
    def _generate_index(
        self,
        server_dir: Path,
        tools: List[Dict[str, Any]],
        server_name: str
    ):
        """Генерировать index.ts для server"""
        
        exports = []
        for tool in tools:
            tool_name = self._sanitize_tool_name(tool['name'])
            exports.append(
                f"export {{ {tool_name} }} from './{tool_name}.ts';"
            )
        
        index_content = f"""/**
 * {server_name.upper()} MCP Server API
 * 
 * Auto-generated from MCP tool definitions
 * Generated: {self._get_timestamp()}
 */

{chr(10).join(exports)}
"""
        
        index_path = server_dir / 'index.ts'
        index_path.write_text(index_content, encoding='utf-8')
    
    def _generate_tool_file(
        self,
        server_dir: Path,
        tool: Dict[str, Any],
        server_name: str
    ):
        """Генерировать файл для одного tool"""
        
        tool_name = self._sanitize_tool_name(tool['name'])
        file_path = server_dir / f"{tool_name}.ts"
        
        # Генерировать interfaces
        interfaces = self._generate_interfaces(tool, tool_name)
        
        # Генерировать function
        function = self._generate_function(tool, tool_name, server_name)
        
        # Собрать всё вместе
        code = f"""/**
 * {tool.get('description', tool_name)}
 * 
 * Auto-generated from MCP tool definition
 */

import {{ callMCPTool }} from '../../client.ts';

{interfaces}

{function}
"""
        
        file_path.write_text(code, encoding='utf-8')
    
    def _generate_interfaces(
        self,
        tool: Dict[str, Any],
        tool_name: str
    ) -> str:
        """Генерировать TypeScript interfaces из JSON Schema"""
        
        input_schema = tool.get('inputSchema', {})
        properties = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        # Input interface
        input_type_name = self._get_input_type_name(tool_name)
        input_interface = f"export interface {input_type_name} {{\n"
        
        if properties:
            for prop_name, prop_schema in properties.items():
                prop_type = self._json_schema_to_ts_type(prop_schema)
                is_required = prop_name in required
                optional_marker = '' if is_required else '?'
                description = prop_schema.get('description', '')
                
                if description:
                    input_interface += f"  /** {description} */\n"
                
                input_interface += f"  {prop_name}{optional_marker}: {prop_type};\n"
        else:
            # Empty interface
            input_interface += "  // No parameters\n"
        
        input_interface += "}\n\n"
        
        # Return type interface (generic для начала)
        return_type_name = self._get_return_type_name(tool_name)
        return_interface = f"export interface {return_type_name} {{\n"
        return_interface += "  [key: string]: any;\n"
        return_interface += "}\n"
        
        return input_interface + return_interface
    
    def _generate_function(
        self,
        tool: Dict[str, Any],
        tool_name: str,
        server_name: str
    ) -> str:
        """Генерировать TypeScript function для tool"""
        
        input_type = self._get_input_type_name(tool_name)
        return_type = self._get_return_type_name(tool_name)
        description = tool.get('description', '')
        
        # Full tool name: server__tool_name
        full_tool_name = f"{server_name}__{tool['name']}"
        
        function = f"""/**
 * {description}
 */
export async function {tool_name}(
  input: {input_type}
): Promise<{return_type}> {{
  return await callMCPTool<{return_type}>(
    '{full_tool_name}',
    input
  );
}}
"""
        
        return function
    
    def _json_schema_to_ts_type(self, schema: Dict[str, Any]) -> str:
        """Конвертировать JSON Schema type в TypeScript type"""
        
        schema_type = schema.get('type', 'any')
        
        type_map = {
            'string': 'string',
            'number': 'number',
            'integer': 'number',
            'boolean': 'boolean',
            'null': 'null',
        }
        
        if schema_type == 'array':
            items = schema.get('items', {})
            item_type = self._json_schema_to_ts_type(items)
            return f"{item_type}[]"
        
        elif schema_type == 'object':
            # Для object возвращаем generic object или Record
            return 'Record<string, any>'
        
        else:
            return type_map.get(schema_type, 'any')
    
    def _sanitize_tool_name(self, name: str) -> str:
        """Sanitize tool name для использования как function/file name"""
        # Убрать server prefix если есть
        if '__' in name:
            name = name.split('__', 1)[1]
        
        # Convert to camelCase
        parts = name.replace('-', '_').split('_')
        return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])
    
    def _get_input_type_name(self, tool_name: str) -> str:
        """Получить имя для Input type"""
        return f"{tool_name[0].upper()}{tool_name[1:]}Input"
    
    def _get_return_type_name(self, tool_name: str) -> str:
        """Получить имя для Return type"""
        return f"{tool_name[0].upper()}{tool_name[1:]}Result"
    
    def _get_timestamp(self) -> str:
        """Получить текущий timestamp для documentation"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_all_servers(
    servers_config: Dict[str, List[Dict[str, Any]]],
    output_dir: str = "./execution-env/servers"
):
    """
    Генерировать TypeScript API для всех MCP servers
    
    Args:
        servers_config: Dict вида:
            {
                '1c': [tool1, tool2, ...],
                'neo4j': [tool1, tool2, ...],
                ...
            }
        output_dir: Output directory
    """
    
    generator = MCPCodeGenerator(output_dir)
    
    total_tools = 0
    
    for server_name, tools in servers_config.items():
        generator.generate_from_mcp_server(server_name, tools)
        total_tools += len(tools)
    
    logger.info(
        f"✅ Generation complete! "
        f"Generated {total_tools} tools for {len(servers_config)} servers"
    )
    
    return total_tools


# Example usage
if __name__ == "__main__":
    # Example MCP tool definition
    example_tools = [
        {
            'name': 'get_configuration',
            'description': 'Get 1C configuration metadata',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Configuration name'
                    },
                    'include_metadata': {
                        'type': 'boolean',
                        'description': 'Include full metadata'
                    }
                },
                'required': ['name']
            }
        },
        {
            'name': 'execute_query',
            'description': 'Execute SQL query in 1C database',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'SQL query'
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Result limit'
                    }
                },
                'required': ['query']
            }
        }
    ]
    
    # Generate
    generator = MCPCodeGenerator()
    generator.generate_from_mcp_server('1c', example_tools)
    
    print("✅ Example generation complete!")
    print("📁 Check ./execution-env/servers/1c/")


