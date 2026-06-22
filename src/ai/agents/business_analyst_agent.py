"""
Business Analyst AI Agent
AI ассистент для бизнес-аналитиков
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BusinessAnalystAgent:
    """AI агент для бизнес-аналитиков"""

    def __init__(self):
        self.agent_name = "local-business-analyst"

    def _extract_items(self, text: str) -> List[str]:
        items: List[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*•]\s*", "", line)
            line = re.sub(r"^\d+[.)]\s*", "", line)
            if line.lower() in {"система должна:", "требования:", "критерии приемки:"}:
                continue
            items.append(line)

        if not items and text.strip():
            items = [
                part.strip()
                for part in re.split(r"(?<=[.!?])\s+", text.strip())
                if part.strip()
            ]
        return items

    def _extract_acceptance_criteria(self, items: List[str]) -> List[str]:
        markers = ("критер", "приемк", "приёмк", "acceptance", "должен", "должна")
        return [
            item for item in items if any(marker in item.lower() for marker in markers)
        ]

    def _is_non_functional(self, item: str) -> bool:
        markers = (
            "производитель",
            "секунд",
            "мс",
            "пользовател",
            "нагруз",
            "безопас",
            "аудит",
            "доступ",
            "отказоуст",
            "availability",
            "performance",
            "security",
            "sla",
        )
        lower = item.lower()
        return any(marker in lower for marker in markers)

    def _source_excerpt(self, text: str) -> str:
        return " ".join(text.split())[:240]

    def _markdown_list(self, items: List[str], empty: str) -> str:
        if not items:
            return f"- {empty}"
        return "\n".join(f"- {item}" for item in items)

    async def analyze_requirements(self, text: str) -> Dict[str, Any]:
        """
        Анализирует требования из текста

        Args:
            text: Текст с требованиями (ТЗ, письмо, и т.д.)

        Returns:
            Структурированные требования
        """
        items = self._extract_items(text)
        user_stories = await self.extract_user_stories(text)
        acceptance_criteria = self._extract_acceptance_criteria(items)
        non_functional = [
            item
            for item in items
            if self._is_non_functional(item) and item not in acceptance_criteria
        ]
        functional = [
            item
            for item in items
            if item not in non_functional and item not in acceptance_criteria
        ]
        coverage = "source_text" if text.strip() else "no_source_text"
        caveats = []
        if not text.strip():
            caveats.append("Не передан текст требований; нечего извлекать.")
        if not user_stories:
            caveats.append("Явные user stories не найдены в источнике.")

        return {
            "agent": self.agent_name,
            "mode": "offline_evidence_extraction",
            "coverage": coverage,
            "functional_requirements": functional,
            "non_functional_requirements": non_functional,
            "user_stories": user_stories,
            "acceptance_criteria": acceptance_criteria,
            "source_excerpt": self._source_excerpt(text),
            "caveats": caveats,
            "summary": {
                "total_requirements": len(functional)
                + len(non_functional)
                + len(acceptance_criteria),
                "functional": len(functional),
                "non_functional": len(non_functional),
                "acceptance_criteria": len(acceptance_criteria),
                "user_stories": len(user_stories),
            },
        }

    async def generate_technical_spec(self, requirements: str) -> str:
        """
        Генерирует техническое задание

        Args:
            requirements: Входные требования

        Returns:
            Техническое задание в markdown
        """
        analysis = await self.analyze_requirements(requirements)
        spec = f"""# Техническое задание

## 1. Цель проекта

{self._source_excerpt(requirements) or "Источник требований не передан."}

## 2. Функциональные требования

{self._markdown_list(analysis["functional_requirements"], "В источнике не выявлены функциональные требования.")}

## 3. Нефункциональные требования

{self._markdown_list(analysis["non_functional_requirements"], "В источнике не выявлены нефункциональные требования.")}

## 4. User stories

{self._markdown_list([f"Как {story['as_a']}, я хочу {story['i_want']}, чтобы {story['so_that']}" for story in analysis["user_stories"]], "В источнике не выявлены явные user stories.")}

## 5. Критерии приемки

{self._markdown_list(analysis["acceptance_criteria"], "В источнике не выявлены критерии приемки.")}

## 6. Caveats

{self._markdown_list(analysis["caveats"], "Caveats отсутствуют для переданного источника.")}
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
        pattern = re.compile(
            r"как\s+(?P<as_a>[^,.]+)[,]?\s+я\s+хочу\s+"
            r"(?P<i_want>.*?)(?:,\s*чтобы\s+(?P<so_that>[^.]+))?(?:\.|$)",
            re.IGNORECASE | re.DOTALL,
        )
        stories = []
        for idx, match in enumerate(pattern.finditer(requirements), 1):
            stories.append(
                {
                    "id": f"US-{idx}",
                    "as_a": " ".join(match.group("as_a").split()),
                    "i_want": " ".join(match.group("i_want").split()),
                    "so_that": " ".join((match.group("so_that") or "").split()),
                    "acceptance_criteria": [],
                    "coverage": "explicit_source_story",
                }
            )
        return stories

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
        items = self._extract_items(process_description)
        stories = await self.extract_user_stories(process_description)
        actors = sorted({story["as_a"] for story in stories if story.get("as_a")})
        steps = [
            {"step": idx, "actor": None, "action": item, "system": None}
            for idx, item in enumerate(items, 1)
        ]
        bpmn_lines = ["```plantuml", "@startuml", "start"]
        for item in items[:12]:
            bpmn_lines.append(f":{item.replace(':', ' -')};")
        bpmn_lines.extend(["stop", "@enduml", "```"])
        return {
            "agent": self.agent_name,
            "mode": "offline_evidence_extraction",
            "coverage": "source_text"
            if process_description.strip()
            else "no_source_text",
            "process_name": "Процесс из переданного описания",
            "actors": actors,
            "steps": steps,
            "bottlenecks": [],
            "improvements": [],
            "bpmn_diagram": "\n".join(bpmn_lines),
            "caveats": [
                "Bottlenecks и improvements не вычисляются без метрик, интервью или event log."
            ],
        }

    async def generate_use_cases(self, feature: str) -> str:
        """
        Генерирует use case диаграмму

        Args:
            feature: Описание функции

        Returns:
            PlantUML код диаграммы
        """
        stories = await self.extract_user_stories(feature)
        actor_labels = [story["as_a"] for story in stories] or ["Пользователь"]
        use_case_labels = [story["i_want"] for story in stories] or [
            self._source_excerpt(feature) or "Уточнить сценарий"
        ]
        lines = [
            "@startuml",
            "left to right direction",
        ]
        for idx, actor in enumerate(actor_labels, 1):
            lines.append(f'actor "{actor.replace(chr(34), "")}" as actor{idx}')
        lines.append('rectangle "Граница функции из источника" {')
        for idx, use_case in enumerate(use_case_labels, 1):
            lines.append(f'  usecase "{use_case.replace(chr(34), "")}" as UC{idx}')
        lines.append("}")
        for idx in range(1, len(use_case_labels) + 1):
            lines.append(f"actor1 --> UC{idx}")
        lines.append("@enduml")
        return "\n".join(lines)


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
