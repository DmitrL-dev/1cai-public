import asyncio
import logging
from unittest.mock import patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def verify_devops_agent():
    print("\n🔍 Verifying DevOpsAgentExtended components...")
    
    try:
        # Mock StructuredLogger to avoid issues
        with patch('src.utils.structured_logging.StructuredLogger') as mock_logger:
            mock_logger.return_value.logger = logging.getLogger("MockLogger")
            
            from src.ai.agents.devops_agent_extended import (
                CICDPipelineOptimizer,
                LogAnalyzer,
                CostOptimizer,
                IaCGenerator
            )
            
            # 1. CICDPipelineOptimizer
            optimizer = CICDPipelineOptimizer()
            metrics = {
                "total_duration": 2000,
                "build_time": 400,
                "test_time": 1200,
                "deploy_time": 400
            }
            analysis = await optimizer.analyze_pipeline({}, metrics)
            print(f"✅ CICDPipelineOptimizer analyzed pipeline (Health: {analysis['overall_health']})")
            
            recommendations = await optimizer.recommend_optimizations({}, metrics)
            print(f"✅ CICDPipelineOptimizer generated {len(recommendations)} recommendations")
            
            # 2. LogAnalyzer
            analyzer = LogAnalyzer()
            logs = """
            2023-10-27 10:00:00 ERROR OutOfMemoryError: Java heap space
            2023-10-27 10:01:00 WARN Slow query detected
            2023-10-27 10:02:00 ERROR Connection refused to database
            """
            log_analysis = await analyzer.analyze_logs(logs)
            print(f"✅ LogAnalyzer found {log_analysis['summary']['errors_found']} errors")
            
            # 3. CostOptimizer
            cost_opt = CostOptimizer()
            setup = {"instance_type": "m5.2xlarge", "instance_count": 5}
            usage = {"cpu_avg": 10, "memory_avg": 20}
            cost_analysis = await cost_opt.analyze_costs(setup, usage)
            print(f"✅ CostOptimizer calculated savings: ${cost_analysis['total_savings_month']}/month")
            
            # 4. IaCGenerator
            iac_gen = IaCGenerator()
            reqs = {"services": ["compute", "database"], "environment": "staging"}
            tf_files = await iac_gen.generate_terraform(reqs)
            print(f"✅ IaCGenerator generated {len(tf_files)} Terraform files")
            
    except Exception as e:
        print(f"❌ DevOpsAgent verification failed: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(verify_devops_agent())
