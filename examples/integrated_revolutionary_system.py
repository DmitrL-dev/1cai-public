
"""
Integrated Revolutionary System - Пример интеграции всех компонентов
===================================================================

Демонстрация работы всех революционных компонентов вместе:
1. Event-Driven Architecture
2. Self-Evolving AI
3. Self-Healing Code
4. Distributed Agent Network
5. Code DNA
6. Predictive Generation
"""

import asyncio
import logging

from src.ai.code_dna import CodeDNAEngine
from src.ai.distributed_agent_network import (Agent, AgentNode, AgentRole,
                                              DistributedAgentNetwork, Task)
from src.ai.llm_provider_abstraction import LLMProviderAbstraction
from src.ai.predictive_code_generation import (PredictiveCodeGenerator,
                                               Requirement)
from src.ai.self_evolving_ai import SelfEvolvingAI
from src.ai.self_healing_code import SelfHealingCode
from src.infrastructure.event_bus import EventBus, EventPublisher, EventType
from src.infrastructure.event_store import InMemoryEventStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedSystem:
    """Интегрированная система всех революционных компонентов"""
    
    def __init__(self):
        # Event-Driven Architecture
        self.event_bus = EventBus()
        self.event_store = InMemoryEventStore()
        self.event_publisher = EventPublisher(self.event_bus, "integrated-system")
        
        # LLM Provider
        self.llm_provider = LLMProviderAbstraction()
        
        # Self-Evolving AI
        self.evolving_ai = SelfEvolvingAI(self.llm_provider, self.event_bus)
        
        # Self-Healing Code
        self.healing_code = SelfHealingCode(self.llm_provider, self.event_bus)
        
        # Distributed Agent Network
        self.agent_network = DistributedAgentNetwork(self.event_bus)
        
        # Code DNA Engine
        self.code_dna_engine = CodeDNAEngine()
        
        # Predictive Generator
        self.predictive_generator = PredictiveCodeGenerator(
            self.llm_provider,
            self.event_bus
        )
    
    async def start(self):
        """Запуск системы"""
        logger.info("Starting Integrated Revolutionary System...")
        
        # Запуск Event Bus
        await self.event_bus.start(num_workers=4)
        
        # Регистрация агентов
        await self._register_agents()
        
        logger.info("System started successfully!")
    
    async def stop(self):
        """Остановка системы"""
        logger.info("Stopping system...")
        await self.event_bus.stop()
        logger.info("System stopped")
    
    async def _register_agents(self):
        """Регистрация агентов в сети"""
        # Developer Agent
        dev_node = AgentNode(
            role=AgentRole.DEVELOPER,
            capabilities={"code_generation", "refactoring"}
        )
        dev_agent = SimpleAgent(dev_node, self.agent_network)
        await self.agent_network.register_agent(dev_agent)
        
        # QA Agent
        qa_node = AgentNode(
            role=AgentRole.QA_ENGINEER,
            capabilities={"testing", "quality_assurance"}
        )
        qa_agent = SimpleAgent(qa_node, self.agent_network)
        await self.agent_network.register_agent(qa_agent)
    
    async def demonstrate_event_driven(self):
        """Демонстрация Event-Driven Architecture"""
        logger.info("=== Event-Driven Architecture Demo ===")
        
        # Публикация события
        event = await self.event_publisher.publish(
            EventType.ML_TRAINING_STARTED,
            payload={"model": "classification", "dataset": "train.csv"}
        )
        
        # Сохранение в Event Store
        await self.event_store.append("ml-training-stream", event)
        
        logger.info(f"Event published: {event.id}")
        
        # Получение из Event Store
        stream = await self.event_store.get_stream("ml-training-stream")
        logger.info(f"Events in stream: {len(stream.events)}")
    
    async def demonstrate_self_evolving(self):
        """Демонстрация Self-Evolving AI"""
        logger.info("=== Self-Evolving AI Demo ===")
        
        # Запуск эволюции
        result = await self.evolving_ai.evolve()
        
        logger.info(f"Evolution status: {result['status']}")
        logger.info(f"Improvements applied: {result.get('improvements_applied', 0)}")
    
    async def demonstrate_self_healing(self):
        """Демонстрация Self-Healing Code"""
        logger.info("=== Self-Healing Code Demo ===")
        
        # Симуляция ошибки
        try:
            raise ValueError("Test error for self-healing")
        except Exception as e:
            fix = await self.healing_code.handle_error(
                e,
                context={
                    "file_path": "examples/test.py",
                    "line_number": 42,
                    "code_snippet": "result = some_function()"
                }
            )
            
            if fix:
                logger.info(f"Fix applied: {fix.id}")
            else:
                logger.info("No fix generated")
        
        # Статистика
        stats = self.healing_code.get_healing_stats()
        logger.info(f"Healing stats: {stats}")
    
    async def demonstrate_distributed_network(self):
        """Демонстрация Distributed Agent Network"""
        logger.info("=== Distributed Agent Network Demo ===")
        
        # Создание задачи
        task = Task(
            description="Generate test code for new feature",
            requirements={"capabilities": ["code_generation"]}
        )
        
        # Отправка задачи в сеть
        submitted = await self.agent_network.submit_task(task)
        logger.info(f"Task submitted: {submitted.id}, status: {submitted.status}")
        
        # Ожидание выполнения
        await asyncio.sleep(0.5)
        
        # Статистика сети
        stats = self.agent_network.get_network_stats()
        logger.info(f"Network stats: {stats}")
    
    async def demonstrate_code_dna(self):
        """Демонстрация Code DNA System"""
        logger.info("=== Code DNA System Demo ===")
        
        sample_code = """
def calculate_sum(a, b):
    return a + b

def calculate_product(a, b):
    return a * b
"""
        
        # Преобразование в ДНК
        dna = self.code_dna_engine.code_to_dna(sample_code)
        logger.info(f"Code converted to DNA: {len(dna.genes)} genes")
        
        # Мутация
        mutated = self.code_dna_engine.mutate(dna)
        logger.info(f"DNA mutated: {len(mutated.mutations)} mutations")
        
        # Обратное преобразование
        code = self.code_dna_engine.dna_to_code(mutated)
        logger.info(f"DNA converted back to code: {len(code)} characters")
    
    async def demonstrate_predictive_generation(self):
        """Демонстрация Predictive Code Generation"""
        logger.info("=== Predictive Code Generation Demo ===")
        
        # Добавление требований
        for i in range(5):
            req = Requirement(
                description=f"Feature requirement {i}",
                category="feature"
            )
            self.predictive_generator.add_requirement(req)
        
        # Предсказание и подготовка
        result = await self.predictive_generator.predict_and_prepare(horizon_days=30)
        
        logger.info(f"Predictions: {result['predictions_count']}")
        logger.info(f"Generated: {result['generated_count']}")
        logger.info(f"Prepared: {result['prepared_count']}")
    
    async def run_full_demo(self):
        """Запуск полной демонстрации"""
        await self.start()
        
        try:
            await self.demonstrate_event_driven()
            await asyncio.sleep(0.5)
            
            await self.demonstrate_self_evolving()
            await asyncio.sleep(0.5)
            
            await self.demonstrate_self_healing()
            await asyncio.sleep(0.5)
            
            await self.demonstrate_distributed_network()
            await asyncio.sleep(0.5)
            
            await self.demonstrate_code_dna()
            await asyncio.sleep(0.5)
            
            await self.demonstrate_predictive_generation()
            
        finally:
            await self.stop()


class SimpleAgent(Agent):
    """Простой агент для демонстрации"""
    
    async def process_task(self, task: Task) -> any:
        """Обработка задачи"""
        logger.info(f"Agent {self.node.role.value} processing task: {task.id}")
        return {"status": "completed", "result": "mock result"}
    
    async def share_knowledge(self, knowledge: dict) -> None:
        """Обмен знаниями"""
        logger.info(f"Agent {self.node.role.value} received knowledge")


async def main():
    """Главная функция"""
    system = IntegratedSystem()
    await system.run_full_demo()


if __name__ == "__main__":
    asyncio.run(main())

