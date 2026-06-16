
#!/usr/bin/env python3
"""
Статистика использования типов данных в конфигурации 1С.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, Tuple


def load_parse_results(parse_path: Path) -> Dict[str, Any]:
    if not parse_path.exists():
        raise FileNotFoundError(
            f"Файл {parse_path} не найден. Запустите парсер EDT перед анализом типов." ""
        )

    try:
        with parse_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError as err:
        raise ValueError(f"Повреждён JSON ({parse_path}): {err}") from err


def _collect_type_stats(attributes: Iterable[Dict[str, Any]]) -> Tuple[Counter, defaultdict[int, int], list[int], list[int]]:
    type_usage: Counter[str] = Counter()
    composite_types: defaultdict[int, int] = defaultdict(int)
    string_lengths: list[int] = []
    number_precisions: list[int] = []

    for attr in attributes:
        type_info = attr.get("type", {}) or {}
        types = type_info.get("types", []) or []

        if types:
            type_usage.update(types)
            if len(types) > 1:
                composite_types[len(types)] += 1

        string_qual = type_info.get("string_qualifiers") or {}
        length = string_qual.get("length")
        if length:
            try:
                string_lengths.append(int(length))
            except ValueError:
                pass

        number_qual = type_info.get("number_qualifiers") or {}
        precision = number_qual.get("precision")
        if precision:
            try:
                number_precisions.append(int(precision))
            except ValueError:
                pass

    return type_usage, composite_types, string_lengths, number_precisions


def analyze_types_for_entities(entities: Iterable[Dict[str, Any]], label: str) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print(f"{label.upper()}")
    print("=" * 80)

    type_usage: Counter[str] = Counter()
    composite_types: defaultdict[int, int] = defaultdict(int)
    string_lengths: list[int] = []
    number_precisions: list[int] = []

    entities_with_metadata = 0
    total_items = 0

    for entity in entities:
        metadata = entity.get("metadata")
        if not metadata:
            continue
        entities_with_metadata += 1

        attr_stats = _collect_type_stats(metadata.get("attributes", []))
        tab_stats = _collect_type_stats(
            column
            for section in metadata.get("tabular_sections", []) or []
            for column in section.get("columns", []) or []
        )

        for counter, composite, lengths, precisions in (attr_stats, tab_stats):
            type_usage.update(counter)
            for count, val in composite.items():
                composite_types[count] += val
            string_lengths.extend(lengths)
            number_precisions.extend(precisions)
            total_items += sum(counter.values())

    print(f"\nВсего объектов: {len(list(entities))}")
    print(f"С метаданными: {entities_with_metadata}")
    print(f"Всего реквизитов/колонок: {total_items}")

    top_types = type_usage.most_common(30)
    if top_types:
        print("\nТОП-30 используемых типов:")
        for idx, (name, count) in enumerate(top_types, 1):
            pct = count / total_items * 100 if total_items else 0
            print(f"  {idx:2d}. {name:<50} {count:>5} ({pct:>5.1f}%)")

    if string_lengths:
        print("\nСтроковые типы:")
        print(f"  Средняя длина: {round(mean(string_lengths))}")
        print(f"  Максимальная длина: {max(string_lengths)}")

    if number_precisions:
        print("\nЧисловые типы:")
        print(f"  Средняя точность: {mean(number_precisions):.1f}")
        print(f"  Максимальная точность: {max(number_precisions)}")

    if composite_types:
        print("\nСоставные типы:")
        for count, usage in sorted(composite_types.items()):
            print(f"  {count} типов: {usage:,} реквизитов")

    return {
        "entities_with_metadata": entities_with_metadata,
        "total_items": total_items,
        "type_usage": dict(type_usage),
        "composite_types": dict(composite_types),
        "avg_string_length": round(mean(string_lengths)) if string_lengths else 0,
        "avg_number_precision": mean(number_precisions) if number_precisions else 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Статистика типов данных конфигурации 1С")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./output/edt_parser/full_parse_with_metadata.json"),
        help="Путь к результатам парсинга EDT",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/analysis/data_types_statistics.json"),
        help="Файл для сохранения результатов",
    )
    parser.add_argument(
        "--config-name",
        default="Configuration",
        help="Имя конфигурации для заголовков",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 80)
    print(f"СТАТИСТИКА ТИПОВ ДАННЫХ ДЛЯ {args.config_name.upper()}")
    print("=" * 80)

    try:
        data = load_parse_results(args.input)
    except (FileNotFoundError, ValueError) as err:
        print(f"Ошибка: {err}")
        return 1

    catalogs_stats = analyze_types_for_entities(data.get("catalogs", []), "Типы данных в справочниках")
    documents_stats = analyze_types_for_entities(data.get("documents", []), "Типы данных в документах")

    results = {
        "schema_version": "1.0.0",
        "config_name": args.config_name,
        "catalogs": catalogs_stats,
        "documents": documents_stats,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(results, fp, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("АНАЛИЗ ТИПОВ ЗАВЕРШЕН")
    print("=" * 80)
    print(f"\nРезультаты сохранены: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())




