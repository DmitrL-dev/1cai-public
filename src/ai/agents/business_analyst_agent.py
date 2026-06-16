
"""
Business Analyst AI Agent
AI ассистент для бизнес-аналитиков
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BusinessAnalystAgent:
    """AI агент для бизнес-аналитиков"""

    def __init__(self):
        self.agent_name = "gigachat"  # TODO: Replace with real GigaChat integration

    async def analyze_requirements(self, text: str) -> Dict[str, Any]:
        """
        Анализирует требования из текста

        Args:
            text: Текст с требованиями (ТЗ, письмо, и т.д.)

        Returns:
            Структурированные требования
        """
        # TODO: Интеграция с GigaChat/YandexGPT

        # Placeholder
        return {
            "functional_requirements": [
                "Реализовать модуль продаж",
                "Добавить отчет по товарам",
                "Интеграция с 1С:УНФ",
            ],
            "non_functional_requirements": [
                "Производительность: < 2 сек на запрос",
                "Поддержка 100+ пользователей",
            ],
            "user_stories": [
                {
                    "as_a": "Менеджер по продажам",
                    "i_want": "Создавать заказы клиентов",
                    "so_that": "Отслеживать продажи",
                }
            ],
            "acceptance_criteria": [
                "Заказ создается за 3 клика",
                "Все обязательные поля проверяются",
                "PDF печатная форма генерируется",
            ],
        }

    async def generate_technical_spec(self, requirements: str) -> str:
        """
        Генерирует техническое задание

        Args:
            requirements: Входные требования

        Returns:
            Техническое задание в markdown
        """
        spec = f"""# Техническое задание

## 1. Цель проекта

{requirements}

## 2. Функциональные требования

### 2.1. Основная функциональность
- Создание заказов клиентов
- Формирование отчетов
- Интеграция с внешними системами

### 2.2. Пользовательский интерфейс
- Форма создания заказа
- Список заказов
- Отчеты по продажам

## 3. Нефункциональные требования

### 3.1. Производительность
- Время отклика: < 2 секунды
- Одновременных пользователей: до 100

### 3.2. Безопасность
- Ролевая модель доступа
- Аудит операций

## 4. Интеграции

- 1С:УНФ
- Внешние API

## 5. Сроки и этапы

| Этап | Описание | Срок |
|------|----------|------|
| 1 | Проектирование | 2 недели |
| 2 | Разработка | 4 недели |
| 3 | Тестирование | 2 недели |
| 4 | Внедрение | 1 неделя |

## 6. Критерии приемки

- [ ] Все функции работают согласно требованиям
- [ ] Производительность соответствует нормативам
- [ ] Пройдены все тесты
- [ ] Документация готова

## 7. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Задержка интеграции | Средняя | Высокое | Параллельная разработка |
| Изменение требований | Высокая | Среднее | Agile подход |
"""
        return spec

    async def extract_user_stories(self, requirements: str) -> List[Dict[str, str]]:
        """
        Извлекает user stories из требований

        Args:
            requirements: Текст требований

        Returns:
            Список user stories
        """
        return [
            {
                "id": "US-1",
                "as_a": "Менеджер по продажам",
                "i_want": "Создавать заказы клиентов через удобную форму",
                "so_that": "Быстро оформлять продажи и избегать ошибок",
                "acceptance_criteria": [
                    "Форма открывается за 1 клик",
                    "Все поля с автозаполнением",
                    "Валидация данных в реальном времени",
                ],
            },
            {
                "id": "US-2",
                "as_a": "Руководитель отдела",
                "i_want": "Видеть отчет по продажам за период",
                "so_that": "Анализировать эффективность отдела",
                "acceptance_criteria": [
                    "Отчет строится за < 5 секунд",
                    "Группировка по менеджерам и товарам",
                    "Экспорт в Excel",
                ],
            },
            {
                "id": "US-3",
                "as_a": "Бухгалтер",
                "i_want": "Получать данные о продажах в 1С:Бухгалтерию",
                "so_that": "Автоматически формировать проводки",
                "acceptance_criteria": [
                    "Синхронизация в режиме реального времени",
                    "Логирование всех передач",
                    "Обработка ошибок",
                ],
            },
        ]

    async def analyze_business_process(
        self, process_description: str
    ) -> Dict[str, Any]:
        """
        Анализирует бизнес-процесс

        Args:
            process_description: Описание процесса

        Returns:
            Структурированный анализ
        """
        return {
            "process_name": "Оформление заказа клиента",
            "actors": ["Менеджер по продажам", "Клиент", "Склад", "Бухгалтерия"],
            "steps": [
                {
                    "step": 1,
                    "actor": "Клиент",
                    "action": "Отправляет заявку",
                    "system": "CRM",
                },
                {
                    "step": 2,
                    "actor": "Менеджер",
                    "action": "Создает заказ в 1С",
                    "system": "1С:УПП",
                },
                {
                    "step": 3,
                    "actor": "Склад",
                    "action": "Резервирует товар",
                    "system": "1С:WMS",
                },
                {
                    "step": 4,
                    "actor": "Бухгалтерия",
                    "action": "Формирует счет",
                    "system": "1С:Бухгалтерия",
                },
            ],
            "bottlenecks": ["Ручной ввод данных заказа", "Проверка наличия товара"],
            "improvements": [
                "Автоматический импорт заявок из CRM",
                "Интеграция с системой управления складом",
                "Электронная подпись документов",
            ],
            "bpmn_diagram": "```plantuml\n@startuml\nstart\n:Клиент отправляет заявку;\n:Менеджер создает заказ;\n:Склад резервирует товар;\n:Бухгалтерия формирует счет;\nstop\n@enduml\n```",
        }

    async def generate_use_cases(self, feature: str) -> str:
        """
        Генерирует use case диаграмму

        Args:
            feature: Описание функции

        Returns:
            PlantUML код диаграммы
        """
        return """@startuml
left to right direction
actor "Менеджер" as manager
actor "Клиент" as client
actor "Бухгалтер" as accountant

rectangle "Система продаж" {
  usecase "Создать заказ" as UC1
  usecase "Просмотреть заказы" as UC2
  usecase "Сформировать счет" as UC3
  usecase "Отправить email" as UC4
  usecase "Оплатить заказ" as UC5
}

manager --> UC1
manager --> UC2
manager --> UC3
client --> UC5
accountant --> UC3
UC1 ..> UC4 : <<include>>
UC5 ..> UC3 : <<extend>>

@enduml"""


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = BusinessAnalystAgent()

        # Test 1: Analyze requirements
        print("=== Test 1: Analyze Requirements ===")
        requirements = await agent.analyze_requirements("Нужна система продаж")
        print(f"User Stories: {len(requirements['user_stories'])}")

        # Test 2: Generate spec
        print("\n=== Test 2: Generate Technical Spec ===")
        spec = await agent.generate_technical_spec("Автоматизация продаж")
        print(spec[:200] + "...")

        # Test 3: User stories
        print("\n=== Test 3: Extract User Stories ===")
        stories = await agent.extract_user_stories("...")
        for story in stories:
            print(f"- {story['id']}: {story['as_a']} хочет {story['i_want']}")

    asyncio.run(test())
