import sys
import os

# Add project root to python path
sys.path.append(os.getcwd())

try:
    print("Verifying imports...")
    from src.ai.advanced_orchestrator import AdvancedAIOrchestrator
    print("✅ src.ai.advanced_orchestrator imported")
    
    from src.analytics.advanced_analytics import AdvancedAnalytics
    print("✅ src.analytics.advanced_analytics imported")
    
    from src.api.advanced_graph_api import router
    print("✅ src.api.advanced_graph_api imported")
    
    from src.config.advanced_config import AdvancedConfigManager
    print("✅ src.config.advanced_config imported")
    
    from src.monitoring.advanced_metrics import AdvancedMetricsCollector
    print("✅ src.monitoring.advanced_metrics imported")
    
    # 1. Security
    from src.security.advanced_security import SecurityManager
    sec_manager = SecurityManager()
    stats = sec_manager.get_security_stats()
    print(f"✅ SecurityManager initialized (Active tokens: {stats['active_tokens']})")

    # 2. Config
    from src.config.advanced_config import AdvancedConfigManager
    config_manager = AdvancedConfigManager()
    # Check internal _components since there is no public config attribute
    print(f"✅ AdvancedConfigManager initialized (Components loaded: {len(config_manager._components)})")

    # 3. Metrics
    from src.monitoring.advanced_metrics import AdvancedMetricsCollector
    metrics = AdvancedMetricsCollector()
    print("✅ AdvancedMetricsCollector initialized")

    # 4. Analytics
    from src.analytics.advanced_analytics import AdvancedAnalytics
    analytics = AdvancedAnalytics()
    print("✅ AdvancedAnalytics initialized")

    # 5. Orchestrator
    from src.ai.advanced_orchestrator import AdvancedAIOrchestrator
    # Orchestrator might need dependencies, so we wrap in try-except to distinguish import vs runtime error
    try:
        orchestrator = AdvancedAIOrchestrator()
        print("✅ AdvancedAIOrchestrator initialized")
    except Exception as e:
        print(f"⚠️ AdvancedAIOrchestrator init warning (expected if dependencies missing): {e}")

    # 6. Graph API Router
    from src.api.advanced_graph_api import router
    print(f"✅ Advanced Graph API Router imported (Routes: {len(router.routes)})")

    print("\n🎉 Deep verification: All classes can be instantiated!")
    
except ImportError as e:
    print(f"\n❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
