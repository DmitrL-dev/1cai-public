
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class SkillSummary:
    skill: str
    count: int


def load_snapshot(base_dir: Path, collector: str) -> Iterable[Dict]:
    collector_path = base_dir / collector
    if not collector_path.exists():
        return []
    dated_dirs = sorted([p for p in collector_path.iterdir() if p.is_dir()], reverse=True)
    records: List[Dict] = []
    for dated in dated_dirs:
        for json_file in sorted(dated.glob("*.json"), reverse=True):
            try:
                payload = json.loads(json_file.read_text(encoding="utf-8"))
                records.extend(payload.get("records", []))
            except (json.JSONDecodeError, OSError):
                continue
        if records:
            break
    return records


def summarize_skills(records: Iterable[Dict]) -> List[SkillSummary]:
    counter: Counter[str] = Counter()
    for record in records:
        for skill in record.get("skills", []):
            counter[skill.strip()] += 1
    return [SkillSummary(skill=k, count=v) for k, v in counter.most_common()]


def render_markdown(skills: List[SkillSummary], conferences: Iterable[Dict]) -> str:
    lines = [
        "# BA Assessment Auto Insights",
        "",
        "## Топ навыков (Job Market)",
        "",
    ]
    if skills:
        for idx, summary in enumerate(skills[:15], start=1):
            lines.append(f"{idx}. {summary.skill} — {summary.count}")
    else:
        lines.append("_Нет данных. Запустите пайплайн job_market._")

    lines.extend(["", "## Конференции / Тренды", ""])
    count = 0
    for item in conferences:
        event = item.get("event", "Unknown event")
        topic = item.get("topic", "Без темы")
        link = item.get("link", "")
        if link:
            lines.append(f"- **{event}**: {topic} ([link]({link}))")
        else:
            lines.append(f"- **{event}**: {topic}")
        count += 1
        if count >= 10:
            break
    if count == 0:
        lines.append("_Нет актуальных конференций. Добавьте источники в BA_CONFERENCE_FEED._")

    lines.extend(
        [
            "",
            "## Рекомендации по обновлению assessment",
            "",
            "- Обновить раздел hard skills с учётом топовых навыков.",
            "- Добавить вопросы по трендовым темам из конференций.",
            "- Приоритизировать обучение согласно частоте навыков.",
        ]
    )
    return "\n".join(lines)


def generate_assessment(
    *,
    input_dir: Path,
    output_path: Path,
) -> None:
    job_records = list(load_snapshot(input_dir, "job_market"))
    conference_records = list(load_snapshot(input_dir, "conference_digest"))
    skills = summarize_skills(job_records)
    markdown = render_markdown(skills, conference_records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate BA assessment insights.")
    parser.add_argument("--input-dir", default="data/ba_intel", help="Каталог с выгрузками пайплайна (по умолчанию data/ba_intел)")
    parser.add_argument(
        "--output",
        default="docs/assessments/BA_ASSESSMENT_AUTO.md",
        help="Файл для записи рекомендаций (по умолчанию docs/assessments/BA_ASSESSMENT_AUTO.md)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    generate_assessment(input_dir=Path(args.input_dir), output_path=Path(args.output))


if __name__ == "__main__":  # pragma: no cover
    main()

