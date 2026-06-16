import asyncio
import logging
import os
from unittest.mock import patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def verify_config_monitoring():
    print("\n🔍 Verifying Config & Monitoring...")
    
    try:
        # 1. Config Manager
        print("Checking AdvancedConfigManager...")
        from src.config.advanced_config import AdvancedConfigManager
        
        # Test Env Loading
        os.environ["EVENT_DRIVEN_ENABLED"] = "true"
        config_manager = AdvancedConfigManager()
        
        event_config = config_manager.get_component_config("event_driven")
        if event_config and event_config.enabled:
            print("✅ Config loaded from environment correctly")
        else:
            print("❌ Config loading from environment failed")
            
        # Test Update
        config_manager.update_config("event_driven", {"new_setting": 123})
        if config_manager.get_component_config("event_driven").get("new_setting") == 123:
            print("✅ Config update successful")
        else:
            print("❌ Config update failed")
            
        # 2. Metrics Collector
        print("\nChecking AdvancedMetricsCollector...")
        # Mock prometheus_client to avoid registry errors
        with patch('src.monitoring.advanced_metrics.Counter'), \
             patch('src.monitoring.advanced_metrics.Gauge'), \
             patch('src.monitoring.advanced_metrics.Histogram'):
            
            from src.monitoring.advanced_metrics import AdvancedMetricsCollector
            
            collector = AdvancedMetricsCollector()
            
            # Test Collection
            collector.collect_event_metrics("test_event", "test_source", 0.5)
            print("✅ collect_event_metrics executed")
            
            collector.collect_evolution_metrics("completed", 5, 2, 0.9)
            print("✅ collect_evolution_metrics executed")
            
            summary = collector.get_summary()
            if isinstance(summary, dict):
                print("✅ get_summary returned dict")
            else:
                print("❌ get_summary failed")

    except Exception as e:
        print(f"❌ Config & Monitoring verification failed: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(verify_config_monitoring())
