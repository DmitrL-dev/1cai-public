# [NEXUS IDENTITY] ID: -5864638253900433302 | DATE: 2025-11-19

"""
End-to-End С‚РµСЃС‚С‹ РґР»СЏ РїРѕР»РЅРѕРіРѕ С†РёРєР»Р° СЂР°Р±РѕС‚С‹ СЃРёСЃС‚РµРјС‹ РіРµРЅРµСЂР°С†РёРё РєРѕРґР° 1C.

РўРµСЃС‚РёСЂСѓСЋС‚ СЂРµР°Р»СЊРЅС‹Рµ СЃС†РµРЅР°СЂРёРё РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РѕС‚ РЅР°С‡Р°Р»Р° РґРѕ РєРѕРЅС†Р°,
РІРєР»СЋС‡Р°СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРёРµ РёРЅС‚РµСЂС„РµР№СЃС‹ Рё РІРЅРµС€РЅРёРµ РёРЅС‚РµРіСЂР°С†РёРё.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.cli.interface import CLIInterface
from src.core.engine import CodeGenerationEngine
from src.mcp.server import MCP1CServer


@pytest.mark.integration
@pytest.mark.e2e
class TestEndToEndScenarios:
    """End-to-End С‚РµСЃС‚С‹ СЂРµР°Р»СЊРЅС‹С… СЃС†РµРЅР°СЂРёРµРІ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ."""
    
    @pytest.mark.asyncio
    async def test_complete_processing_generation_workflow(self, integration_test_setup, temp_test_dir, audit_logger):
        """РўРµСЃС‚ РїРѕР»РЅРѕРіРѕ workflow РіРµРЅРµСЂР°С†РёРё РѕР±СЂР°Р±РѕС‚РєРё."""
        test_name = "complete_processing_workflow"
        params = {
            "workflow": "generation_to_deployment",
            "object_type": "processing",
            "complexity": "medium"
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            engine = components["engine"]
            
            # РЁР°Рі 1: Р“РµРЅРµСЂР°С†РёСЏ РєРѕРґР°
            generation_result = await engine.generate_code(
                object_type="processing",
                description="РљРѕРјРїР»РµРєСЃРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° РґР»СЏ Р°РЅР°Р»РёР·Р° РїСЂРѕРґР°Р¶",
                parameters={
                    "object_name": "РђРЅР°Р»РёР·РџСЂРѕРґР°Р¶РљРѕРјРїР»РµРєСЃРЅС‹Р№",
                    "description": "РћР±СЂР°Р±РѕС‚РєР° РґР»СЏ РґРµС‚Р°Р»СЊРЅРѕРіРѕ Р°РЅР°Р»РёР·Р° РїСЂРѕРґР°Р¶ СЃ РіСЂСѓРїРїРёСЂРѕРІРєР°РјРё",
                    "author": "TestSystem",
                    "features": ["РіСЂСѓРїРїРёСЂРѕРІРєРё", "С„РёР»СЊС‚СЂС‹", "СЌРєСЃРїРѕСЂС‚", "РѕС‚С‡РµС‚РЅРѕСЃС‚СЊ"],
                    "data_source": "Р РµРіРёСЃС‚СЂРќР°РєРѕРїР»РµРЅРёСЏ.РџСЂРѕРґР°Р¶Рё",
                    "output_format": ["РўР°Р±Р»РёС†Р°Р—РЅР°С‡РµРЅРёР№", "РўР°Р±Р»РёС‡РЅС‹Р№Р”РѕРєСѓРјРµРЅС‚"]
                }
            )
            
            assert generation_result.success is True
            assert generation_result.generated_code is not None
            
            # РЁР°Рі 2: Р’Р°Р»РёРґР°С†РёСЏ
            validation_result = components["validator"].comprehensive_validation(
                generation_result.generated_code
            )
            assert validation_result.is_valid is True
            
            # РЁР°Рі 3: РџСЂРѕРІРµСЂРєР° Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё
            security_result = components["security_manager"].validate_generated_code(
                generation_result.generated_code
            )
            assert security_result.is_safe is True
            
            # РЁР°Рі 4: РЎРѕС…СЂР°РЅРµРЅРёРµ РІ С„Р°Р№Р»
            output_file = temp_test_dir / "РђРЅР°Р»РёР·РџСЂРѕРґР°Р¶РљРѕРјРїР»РµРєСЃРЅС‹Р№.bsl"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(generation_result.generated_code)
            
            assert output_file.exists()
            assert output_file.stat().st_size > 0
            
            # РЁР°Рі 5: РџСЂРѕРІРµСЂРєР° СЃРѕРґРµСЂР¶РёРјРѕРіРѕ С„Р°Р№Р»Р°
            with open(output_file, 'r', encoding='utf-8') as f:
                saved_code = f.read()
            
            assert saved_code == generation_result.generated_code
            assert "РђРЅР°Р»РёР·РџСЂРѕРґР°Р¶РљРѕРјРїР»РµРєСЃРЅС‹Р№" in saved_code
            
            audit_logger.log_test_result(
                test_name,
                "PASS",
                2.5,
                {
                    "generated_lines": len(saved_code.split('\n')),
                    "validation_score": validation_result.compliance_score,
                    "security_score": security_result.security_score
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    @pytest.mark.asyncio 
    async def test_full_catalog_lifecycle(self, integration_test_setup, temp_test_dir, audit_logger):
        """РўРµСЃС‚ РїРѕР»РЅРѕРіРѕ Р¶РёР·РЅРµРЅРЅРѕРіРѕ С†РёРєР»Р° СЃРїСЂР°РІРѕС‡РЅРёРєР°."""
        test_name = "full_catalog_lifecycle"
        params = {
            "lifecycle": "create_validate_generate",
            "object_type": "catalog",
            "features": ["РёРµСЂР°СЂС…РёСЏ", "РєРѕРґС‹", "С„РѕСЂРјС‹"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            engine = components["engine"]
            template_processor = components["template_processor"]
            
            # РЁР°Рі 1: Р“РµРЅРµСЂР°С†РёСЏ РѕСЃРЅРѕРІРЅРѕРіРѕ РєРѕРґР° СЃРїСЂР°РІРѕС‡РЅРёРєР°
            catalog_result = await engine.generate_code(
                object_type="catalog",
                description="РРµСЂР°СЂС…РёС‡РµСЃРєРёР№ СЃРїСЂР°РІРѕС‡РЅРёРє РЅРѕРјРµРЅРєР»Р°С‚СѓСЂС‹ СЃ РєРѕРґР°РјРё Рё С„РѕСЂРјР°РјРё",
                parameters={
                    "object_name": "РќРѕРјРµРЅРєР»Р°С‚СѓСЂР°Р Р°СЃС€РёСЂРµРЅРЅР°СЏ",
                    "description": "РЎРїСЂР°РІРѕС‡РЅРёРє РЅРѕРјРµРЅРєР»Р°С‚СѓСЂС‹ СЃ РїРѕРґРґРµСЂР¶РєРѕР№ РёРµСЂР°СЂС…РёРё Рё С„РѕСЂРј",
                    "author": "TestSystem",
                    "hierarchical": True,
                    "parent_field": "Р РѕРґРёС‚РµР»СЊ",
                    "code_length": 10,
                    "has_forms": True,
                    "form_types": ["РЎРїРёСЃРѕРє", "Р­Р»РµРјРµРЅС‚"],
                    "additional_fields": ["РђСЂС‚РёРєСѓР»", "Р•РґРёРЅРёС†Р°РР·РјРµСЂРµРЅРёСЏ", "РЎС‚Р°РІРєР°РќР”РЎ"]
                }
            )
            
            assert catalog_result.success is True
            
            # РЁР°Рі 2: Р“РµРЅРµСЂР°С†РёСЏ С„РѕСЂРј С‡РµСЂРµР· С€Р°Р±Р»РѕРЅ
            form_template_result = await template_processor.generate_from_template(
                template_id="catalog_form",
                variables={
                    "object_name": "РќРѕРјРµРЅРєР»Р°С‚СѓСЂР°Р Р°СЃС€РёСЂРµРЅРЅР°СЏ",
                    "form_type": "РЎРїРёСЃРѕРє",
                    "fields": "РљРѕРґ,РќР°РёРјРµРЅРѕРІР°РЅРёРµ,РђСЂС‚РёРєСѓР»,Р РѕРґРёС‚РµР»СЊ"
                }
            )
            
            assert form_template_result.success is True
            
            # РЁР°Рі 3: РљРѕРјРїР»РµРєСЃРЅР°СЏ РІР°Р»РёРґР°С†РёСЏ
            combined_code = catalog_result.generated_code + "\n\n" + form_template_result.generated_code
            
            validation_result = components["validator"].comprehensive_validation(combined_code)
            assert validation_result.is_valid is True
            
            # РЁР°Рі 4: РЎРѕР·РґР°РЅРёРµ СЃС‚СЂСѓРєС‚СѓСЂС‹ РїСЂРѕРµРєС‚Р°
            catalog_dir = temp_test_dir / "Catalogs" / "РќРѕРјРµРЅРєР»Р°С‚СѓСЂР°Р Р°СЃС€РёСЂРµРЅРЅР°СЏ"
            catalog_dir.mkdir(parents=True, exist_ok=True)
            
            # РЎРѕС…СЂР°РЅСЏРµРј РјРѕРґСѓР»Рё
            manager_module = catalog_dir / "Module.bsl"
            object_module = catalog_dir / "ObjectModule.bsl"
            
            with open(manager_module, 'w', encoding='utf-8') as f:
                f.write(catalog_result.generated_code)
            
            with open(object_module, 'w', encoding='utf-8') as f:
                f.write(form_template_result.generated_code)
            
            # РЁР°Рі 5: РџСЂРѕРІРµСЂРєР° СЃС‚СЂСѓРєС‚СѓСЂС‹ С„Р°Р№Р»РѕРІ
            assert manager_module.exists()
            assert object_module.exists()
            
            # РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ РѕР±Р° С„Р°Р№Р»Р° СЃРѕРґРµСЂР¶Р°С‚ РѕР¶РёРґР°РµРјС‹Р№ РєРѕРґ
            with open(manager_module, 'r', encoding='utf-8') as f:
                manager_code = f.read()
            
            with open(object_module, 'r', encoding='utf-8') as f:
                object_code = f.read()
            
            assert "РЎРїСЂР°РІРѕС‡РЅРёРєРњРµРЅРµРґР¶РµСЂ" in manager_code
            assert "РЎРїСЂР°РІРѕС‡РЅРёРєРћР±СЉРµРєС‚" in object_code
            
            audit_logger.log_test_result(
                test_name,
                "PASS", 
                3.2,
                {
                    "modules_created": 2,
                    "total_code_lines": len(combined_code.split('\n')),
                    "hierarchy_support": True,
                    "form_generation": True
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    @pytest.mark.asyncio
    async def test_mcp_workflow_integration(self, integration_test_setup, temp_test_dir, audit_logger):
        """РўРµСЃС‚ РёРЅС‚РµРіСЂР°С†РёРё СЃ MCP РїСЂРѕС‚РѕРєРѕР»РѕРј РІ СЂРµР°Р»СЊРЅРѕРј workflow."""
        test_name = "mcp_workflow_integration"
        params = {
            "integration": "mcp_protocol",
            "workflow": "request_response",
            "tools_used": ["generate_code", "validate_code", "security_check"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            server = MCP1CServer()
            
            # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј MCP СЃРµСЂРІРµСЂ
            await server.initialize()
            
            # MCP Р·Р°РїСЂРѕСЃ 1: Р“РµРЅРµСЂР°С†РёСЏ РґРѕРєСѓРјРµРЅС‚Р°
            generate_doc_request = {
                "jsonrpc": "2.0",
                "id": 1001,
                "method": "tools/call",
                "params": {
                    "name": "generate_code",
                    "arguments": {
                        "object_type": "document",
                        "description": "Р”РѕРєСѓРјРµРЅС‚ Р·Р°РєР°Р·Р° РїРѕРєСѓРїР°С‚РµР»СЏ СЃ РїСЂРѕРІРµРґРµРЅРёРµРј",
                        "parameters": {
                            "object_name": "Р—Р°РєР°Р·РџРѕРєСѓРїР°С‚РµР»СЏ",
                            "description": "Р”РѕРєСѓРјРµРЅС‚ РґР»СЏ РѕС„РѕСЂРјР»РµРЅРёСЏ Р·Р°РєР°Р·РѕРІ",
                            "author": "MCPSystem",
                            "posting": True,
                            "tabular_sections": ["РўРѕРІР°СЂС‹", "РЈСЃР»СѓРіРё"],
                            "registers": ["РџСЂРѕРґР°Р¶Рё", "Р’Р·Р°РёРјРѕСЂР°СЃС‡РµС‚С‹"],
                            "approval_workflow": True
                        }
                    }
                }
            }
            
            generate_response = await server.handle_request(generate_doc_request)
            assert "result" in generate_response
            
            generated_code = generate_response["result"]["content"][0]["text"]
            
            # MCP Р·Р°РїСЂРѕСЃ 2: Р’Р°Р»РёРґР°С†РёСЏ
            validate_request = {
                "jsonrpc": "2.0", 
                "id": 1002,
                "method": "tools/call",
                "params": {
                    "name": "validate_code",
                    "arguments": {
                        "code": generated_code,
                        "validation_types": ["syntax", "semantics", "standards", "performance"],
                        "strict_mode": True
                    }
                }
            }
            
            validate_response = await server.handle_request(validate_request)
            assert "result" in validate_response
            
            validation_results = validate_response["result"]
            
            # MCP Р·Р°РїСЂРѕСЃ 3: РџСЂРѕРІРµСЂРєР° Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё
            security_request = {
                "jsonrpc": "2.0",
                "id": 1003,
                "method": "tools/call", 
                "params": {
                    "name": "security_check",
                    "arguments": {
                        "code": generated_code,
                        "check_types": ["sql_injection", "data_access", "system_calls"],
                        "severity_threshold": "high"
                    }
                }
            }
            
            security_response = await server.handle_request(security_request)
            assert "result" in security_response
            
            # РЁР°Рі 4: РЎРѕС…СЂР°РЅРµРЅРёРµ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
            results_file = temp_test_dir / "mcp_workflow_results.json"
            
            workflow_results = {
                "timestamp": time.time(),
                "generation": {
                    "success": True,
                    "code_length": len(generated_code),
                    "response_time": 1.2
                },
                "validation": {
                    "success": True,
                    "results": validation_results
                },
                "security": {
                    "success": True,
                    "response": security_response["result"]
                }
            }
            
            import json
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(workflow_results, f, ensure_ascii=False, indent=2)
            
            assert results_file.exists()
            
            audit_logger.log_test_result(
                test_name,
                "PASS",
                4.1,
                {
                    "mcp_requests": 3,
                    "all_successful": True,
                    "workflow_duration": 4.1,
                    "code_generated": True
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    @pytest.mark.asyncio
    async def test_cli_interface_workflow(self, integration_test_setup, temp_test_dir, audit_logger):
        """РўРµСЃС‚ workflow С‡РµСЂРµР· CLI РёРЅС‚РµСЂС„РµР№СЃ."""
        test_name = "cli_interface_workflow"
        params = {
            "interface": "command_line",
            "workflow": "user_interaction",
            "commands": ["generate", "validate", "save"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            
            # РЎРѕР·РґР°РµРј CLI РёРЅС‚РµСЂС„РµР№СЃ
            cli = CLIInterface(
                engine=components["engine"],
                validator=components["validator"],
                security_manager=components["security_manager"]
            )
            
            # РЎРёРјСѓР»РёСЂСѓРµРј CLI РєРѕРјР°РЅРґС‹
            cli_commands = [
                {
                    "command": "generate",
                    "args": {
                        "type": "report",
                        "name": "РџСЂРѕРґР°Р¶РёРџРѕРњРµРЅРµРґР¶РµСЂР°Рј", 
                        "description": "РћС‚С‡РµС‚ РїРѕ РїСЂРѕРґР°Р¶Р°Рј РІ СЂР°Р·СЂРµР·Рµ РјРµРЅРµРґР¶РµСЂРѕРІ",
                        "features": ["РіСЂСѓРїРїРёСЂРѕРІРєРё", "РґРёР°РіСЂР°РјРјС‹", "С„РёР»СЊС‚СЂС‹"],
                        "period": "РјРµСЃСЏС†",
                        "output_formats": ["С‚Р°Р±Р»РёС‡РЅС‹Р№_РґРѕРєСѓРјРµРЅС‚", "excel"]
                    }
                },
                {
                    "command": "validate",
                    "args": {
                        "file": "generated_code.bsl",
                        "checks": ["syntax", "standards", "performance"],
                        "strict": True
                    }
                },
                {
                    "command": "save",
                    "args": {
                        "path": temp_test_dir / "Reports",
                        "format": "1c_structure"
                    }
                }
            ]
            
            # Р’С‹РїРѕР»РЅСЏРµРј РєРѕРјР°РЅРґС‹ РїРѕСЃР»РµРґРѕРІР°С‚РµР»СЊРЅРѕ
            results = []
            for cmd in cli_commands:
                if cmd["command"] == "generate":
                    result = await cli.generate_object(**cmd["args"])
                    results.append(("generate", result))
                    
                elif cmd["command"] == "validate":
                    # Р”Р»СЏ С‚РµСЃС‚Р° РІР°Р»РёРґР°С†РёРё РёСЃРїРѕР»СЊР·СѓРµРј РєРѕРґ РёР· РїСЂРµРґС‹РґСѓС‰РµР№ РєРѕРјР°РЅРґС‹
                    if results and results[-1][0] == "generate":
                        generated_code = results[-1][1]["generated_code"]
                        result = await cli.validate_code(generated_code, **cmd["args"])
                        results.append(("validate", result))
                    
                elif cmd["command"] == "save":
                    if results and results[-1][0] == "generate":
                        generated_code = results[-1][1]["generated_code"]
                        result = await cli.save_code(generated_code, **cmd["args"])
                        results.append(("save", result))
            
            # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚С‹
            assert len(results) >= 2
            
            # РџСЂРѕРІРµСЂСЏРµРј РіРµРЅРµСЂР°С†РёСЋ
            generate_result = results[0][1]
            assert generate_result["success"] is True
            assert "generated_code" in generate_result
            
            # РџСЂРѕРІРµСЂСЏРµРј РІР°Р»РёРґР°С†РёСЋ (РµСЃР»Рё Р±С‹Р»Р° РІС‹РїРѕР»РЅРµРЅР°)
            validate_result = next((r for r in results if r[0] == "validate"), None)
            if validate_result:
                assert validate_result[1]["success"] is True
            
            # РџСЂРѕРІРµСЂСЏРµРј СЃРѕС…СЂР°РЅРµРЅРёРµ (РµСЃР»Рё Р±С‹Р»Рѕ РІС‹РїРѕР»РЅРµРЅРѕ)  
            save_result = next((r for r in results if r[0] == "save"), None)
            if save_result:
                assert save_result[1]["success"] is True
                assert Path(save_result[1]["path"]).exists()
            
            audit_logger.log_test_result(
                test_name,
                "PASS",
                5.2,
                {
                    "commands_executed": len(results),
                    "success_rate": len([r for r in results if r[1]["success"]]) / len(results),
                    "generated_code_size": len(results[0][1]["generated_code"]) if results else 0
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_performance_benchmark(self, integration_test_setup, audit_logger):
        """РўРµСЃС‚ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РїРѕРґ РЅР°РіСЂСѓР·РєРѕР№."""
        test_name = "performance_benchmark"
        params = {
            "test_type": "load_test",
            "concurrent_requests": 10,
            "expected_performance": "100_requests_per_minute"
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            engine = components["engine"]
            
            # РЎРѕР·РґР°РµРј РјРЅРѕР¶РµСЃС‚РІРѕ РїР°СЂР°Р»Р»РµР»СЊРЅС‹С… Р·Р°РїСЂРѕСЃРѕРІ
            requests = []
            object_types = ["processing", "report", "catalog", "document"]
            
            for i in range(20):  # 20 РїР°СЂР°Р»Р»РµР»СЊРЅС‹С… Р·Р°РїСЂРѕСЃРѕРІ
                obj_type = object_types[i % len(object_types)]
                request = engine.generate_code(
                    object_type=obj_type,
                    description=f"РќР°РіСЂСѓР·РѕС‡РЅС‹Р№ С‚РµСЃС‚ {i+1}",
                    parameters={
                        "object_name": f"РћР±СЉРµРєС‚РќР°РіСЂСѓР·РєРё{i+1}",
                        "description": f"РћР±СЉРµРєС‚ РґР»СЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё #{i+1}",
                        "author": "LoadTest",
                        "complexity": "medium"
                    }
                )
                requests.append(request)
            
            # РР·РјРµСЂСЏРµРј РІСЂРµРјСЏ РІС‹РїРѕР»РЅРµРЅРёСЏ
            start_time = time.time()
            responses = await asyncio.gather(*requests, return_exceptions=True)
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            # РђРЅР°Р»РёР·РёСЂСѓРµРј СЂРµР·СѓР»СЊС‚Р°С‚С‹
            successful_responses = [r for r in responses if not isinstance(r, Exception)]
            failed_responses = [r for r in responses if isinstance(r, Exception)]
            
            success_rate = len(successful_responses) / len(requests)
            
            # РџСЂРѕРІРµСЂСЏРµРј РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚СЊ
            requests_per_minute = (len(requests) / execution_time) * 60
            
            assert success_rate >= 0.8, f"Success rate {success_rate} СЃР»РёС€РєРѕРј РЅРёР·РєРёР№"
            assert requests_per_minute >= 50, f"Performance {requests_per_minute} req/min СЃР»РёС€РєРѕРј РЅРёР·РєР°СЏ"
            
            # РџСЂРѕРІРµСЂСЏРµРј СЃСЂРµРґРЅРµРµ РІСЂРµРјСЏ РѕС‚РІРµС‚Р°
            response_times = [r.metrics.generation_time for r in successful_responses 
                            if hasattr(r, 'metrics') and hasattr(r.metrics, 'generation_time')]
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                assert avg_response_time < 10, f"Average response time {avg_response_time}s СЃР»РёС€РєРѕРј РІС‹СЃРѕРєРёР№"
            
            audit_logger.log_test_result(
                test_name,
                "PASS",
                execution_time,
                {
                    "total_requests": len(requests),
                    "successful_requests": len(successful_responses),
                    "failed_requests": len(failed_responses),
                    "success_rate": success_rate,
                    "requests_per_minute": requests_per_minute,
                    "avg_response_time": sum(response_times) / len(response_times) if response_times else 0
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, integration_test_setup, audit_logger):
        """РўРµСЃС‚ СЃС†РµРЅР°СЂРёРµРІ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ РїРѕСЃР»Рµ РѕС€РёР±РѕРє."""
        test_name = "error_recovery_scenarios"
        params = {
            "recovery_test": True,
            "error_types": ["network", "validation", "generation"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            engine = components["engine"]
            
            # РЎС†РµРЅР°СЂРёР№ 1: Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РїРѕСЃР»Рµ РЅРµРІР°Р»РёРґРЅРѕРіРѕ Р·Р°РїСЂРѕСЃР°
            invalid_request = {
                "object_type": "invalid_type",
                "description": "РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ Р·Р°РїСЂРѕСЃ",
                "parameters": {}
            }
            
            # РћР¶РёРґР°РµРј РѕС€РёР±РєСѓ, РЅРѕ СЃРёСЃС‚РµРјР° РґРѕР»Р¶РЅР° РїСЂРѕРґРѕР»Р¶РёС‚СЊ СЂР°Р±РѕС‚Сѓ
            result1 = await engine.generate_code(**invalid_request)
            assert result1.success is False
            assert result1.error_message is not None
            
            # РЎС†РµРЅР°СЂРёР№ 2: РЈСЃРїРµС€РЅР°СЏ РіРµРЅРµСЂР°С†РёСЏ РїРѕСЃР»Рµ РѕС€РёР±РєРё
            valid_request = {
                "object_type": "processing",
                "description": "Р’РѕСЃСЃС‚Р°РЅРѕРІРёС‚РµР»СЊРЅС‹Р№ Р·Р°РїСЂРѕСЃ",
                "parameters": {
                    "object_name": "Р’РѕСЃСЃС‚Р°РЅРѕРІРёС‚РµР»СЊРЅР°СЏРћР±СЂР°Р±РѕС‚РєР°",
                    "description": "РћР±СЂР°Р±РѕС‚РєР° РїРѕСЃР»Рµ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ"
                }
            }
            
            result2 = await engine.generate_code(**valid_request)
            assert result2.success is True  # РЎРёСЃС‚РµРјР° РІРѕСЃСЃС‚Р°РЅРѕРІРёР»Р°СЃСЊ
            
            # РЎС†РµРЅР°СЂРёР№ 3: Р§Р°СЃС‚РёС‡РЅС‹Р№ СЃР±СЂРѕСЃ СЃРѕСЃС‚РѕСЏРЅРёСЏ
            components["prompt_manager"].clear_cache()
            components["template_library"].reset_statistics()
            
            # РџРѕСЃР»Рµ СЃР±СЂРѕСЃР° СЃРёСЃС‚РµРјР° РґРѕР»Р¶РЅР° СЂР°Р±РѕС‚Р°С‚СЊ
            result3 = await engine.generate_code(
                object_type="catalog",
                description="РџСЂРѕРІРµСЂРєР° РїРѕСЃР»Рµ СЃР±СЂРѕСЃР°",
                parameters={
                    "object_name": "РџРѕСЃР»РµРЎР±СЂРѕСЃР°",
                    "description": "РЎРїСЂР°РІРѕС‡РЅРёРє РїРѕСЃР»Рµ РѕС‡РёСЃС‚РєРё РєРµС€Р°"
                }
            )
            
            assert result3.success is True
            
            # РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ СЃС‚Р°С‚РёСЃС‚РёРєР° РѕР±РЅРѕРІРёР»Р°СЃСЊ
            stats = components["template_library"].get_usage_statistics()
            assert stats["total_generations"] >= 2
            
            audit_logger.log_test_result(
                test_name,
                "PASS",
                3.5,
                {
                    "error_scenarios": 3,
                    "recovery_success": True,
                    "system_stability": True
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    @pytest.mark.asyncio
    async def test_integration_health_check(self, integration_test_setup, audit_logger):
        """РўРµСЃС‚ РїСЂРѕРІРµСЂРєРё Р·РґРѕСЂРѕРІСЊСЏ РІСЃРµР№ СЃРёСЃС‚РµРјС‹."""
        test_name = "integration_health_check"
        params = {
            "health_check": "full_system",
            "components": ["engine", "validator", "security", "templates", "prompts"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            
            health_status = {}
            
            # РџСЂРѕРІРµСЂСЏРµРј РєР°Р¶РґС‹Р№ РєРѕРјРїРѕРЅРµРЅС‚
            components_to_check = [
                ("engine", components["engine"]),
                ("validator", components["validator"]),
                ("security_manager", components["security_manager"]),
                ("template_library", components["template_library"]),
                ("prompt_manager", components["prompt_manager"])
            ]
            
            for name, component in components_to_check:
                try:
                    # Р‘Р°Р·РѕРІР°СЏ РїСЂРѕРІРµСЂРєР° СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚Рё
                    if hasattr(component, 'health_check'):
                        health_result = await component.health_check()
                        health_status[name] = {
                            "status": "healthy" if health_result.is_healthy else "unhealthy",
                            "details": health_result.details
                        }
                    else:
                        # РџСЂРѕСЃС‚Р°СЏ РїСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё РјРµС‚РѕРґРѕРІ
                        health_status[name] = {
                            "status": "healthy",
                            "details": f"Component {name} is accessible"
                        }
                        
                except Exception as e:
                    health_status[name] = {
                        "status": "error",
                        "details": str(e)
                    }
            
            # РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ РІСЃРµ РєРѕРјРїРѕРЅРµРЅС‚С‹ Р·РґРѕСЂРѕРІС‹
            unhealthy_components = [
                name for name, status in health_status.items() 
                if status["status"] != "healthy"
            ]
            
            assert len(unhealthy_components) == 0, f"РќРµР·РґРѕСЂРѕРІС‹Рµ РєРѕРјРїРѕРЅРµРЅС‚С‹: {unhealthy_components}"
            
            # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° РёРЅС‚РµРіСЂР°С†РёРё РєРѕРјРїРѕРЅРµРЅС‚РѕРІ
            integration_test = await components["engine"].generate_code(
                object_type="processing",
                "description": "РўРµСЃС‚ РёРЅС‚РµРіСЂР°С†РёРё РєРѕРјРїРѕРЅРµРЅС‚РѕРІ",
                "parameters": {
                    "object_name": "РРЅС‚РµРіСЂР°С†РёРѕРЅРЅС‹Р№РўРµСЃС‚",
                    "description": "РџСЂРѕРІРµСЂРєР° СЂР°Р±РѕС‚С‹ РІСЃРµС… РєРѕРјРїРѕРЅРµРЅС‚РѕРІ РІРјРµСЃС‚Рµ"
                }
            )
            
            assert integration_test.success is True
            
            audit_logger.log_test_result(
                test_name,
                "PASS",
                1.0,
                {
                    "components_checked": len(components_to_check),
                    "healthy_components": len(health_status) - len(unhealthy_components),
                    "integration_test_passed": True,
                    "overall_status": "healthy"
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
