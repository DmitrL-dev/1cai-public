"""Three-tier domain classifier for BSL modules.

Tier 1: Subsystem XML parsing (structural mapping)
Tier 2: Keyword matching on filepath / object name
Tier 3: Content keyword scan (fallback for unclassified)
"""

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Domain keyword dictionary
# ---------------------------------------------------------------------------

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "Бухгалтерия": [
        "бухгалтер",
        "проводк",
        "счет",
        "субконто",
        "баланс",
        "журналпроводок",
        "регистрбухгалтерии",
        "хозрасчетный",
    ],
    "Налоги": [
        "ндс",
        "налог",
        "декларац",
        "ндфл",
        "фсс",
        "пфр",
        "взнос",
    ],
    "Склад": [
        "склад",
        "номенклатур",
        "остаток",
        "товар",
        "запас",
        "партия",
        "серия",
        "ячейк",
        "ордер",
        "инвентаризац",
    ],
    "Кадры": [
        "кадр",
        "сотрудник",
        "физлиц",
        "штатн",
        "должност",
        "прием",
        "увольнен",
        "отпуск",
        "больничн",
        "стаж",
    ],
    "Зарплата": [
        "зарплат",
        "начислен",
        "удержан",
        "расчетведомост",
        "табель",
    ],
    "Продажи": [
        "продаж",
        "реализац",
        "клиент",
        "покупател",
        "заказпокупател",
        "коммерческ",
        "ценообразован",
        "скидк",
    ],
    "Закупки": [
        "закупк",
        "поставщик",
        "заказпоставщик",
        "снабжен",
    ],
    "Производство": [
        "производств",
        "спецификац",
        "техкарт",
        "маршрут",
        "выпуск",
        "полуфабрикат",
    ],
    "Казначейство": [
        "казначей",
        "платеж",
        "банк",
        "касс",
        "денежн",
        "расчетныйсчет",
    ],
    "МСФО": [
        "мсфо",
        "ifrs",
        "международн",
    ],
    "Администрирование": [
        "администрир",
        "настройк",
        "обновлен",
        "обмендан",
        "загрузк",
        "выгрузк",
        "регламентн",
        "служебн",
    ],
    "Общее": [
        "общегоназначения",
        "строковыефункции",
        "утилит",
    ],
}

# Pre-compile keyword patterns per domain
_DOMAIN_PATTERNS: Dict[str, re.Pattern] = {
    domain: re.compile("|".join(re.escape(kw) for kw in keywords), re.IGNORECASE)
    for domain, keywords in DOMAIN_KEYWORDS.items()
}

# ---------------------------------------------------------------------------
# Metadata object extraction from module_path
# ---------------------------------------------------------------------------

# Maps config folder names → short metadata type names
_FOLDER_TO_META: Dict[str, str] = {
    "Catalogs": "Catalog",
    "Documents": "Document",
    "InformationRegisters": "InformationRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "AccountingRegisters": "AccountingRegister",
    "Enums": "Enum",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "ChartsOfCalculationTypes": "ChartOfCalculationTypes",
    "BusinessProcesses": "BusinessProcess",
    "Tasks": "Task",
    "DataProcessors": "DataProcessor",
    "Reports": "Report",
    "CommonModules": "CommonModule",
    "ExchangePlans": "ExchangePlan",
    "Constants": "Constant",
    "CalculationRegisters": "CalculationRegister",
    "CommonForms": "CommonForm",
    "CommonCommands": "CommonCommand",
    "SettingsStorages": "SettingsStorage",
    "SessionParameters": "SessionParameter",
    "Roles": "Role",
    "CommonTemplates": "CommonTemplate",
    "FilterCriteria": "FilterCriterion",
    "EventSubscriptions": "EventSubscription",
    "ScheduledJobs": "ScheduledJob",
    "FunctionalOptions": "FunctionalOption",
    "FunctionalOptionsParameters": "FunctionalOptionsParameter",
    "DefinedTypes": "DefinedType",
    "Sequences": "Sequence",
    "DocumentJournals": "DocumentJournal",
    "CommandGroups": "CommandGroup",
    "CommonAttributes": "CommonAttribute",
    "Subsystems": "Subsystem",
    "WebServices": "WebService",
    "HTTPServices": "HTTPService",
    "ExternalDataSources": "ExternalDataSource",
}


def _extract_metadata_object(module_path: str) -> Optional[str]:
    """Extract metadata object identifier (e.g. 'Catalog.Номенклатура') from module path."""
    parts = module_path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        folder = parts[0]
        object_name = parts[1]
        meta_type = _FOLDER_TO_META.get(folder)
        if meta_type:
            return f"{meta_type}.{object_name}"
    return None


# ---------------------------------------------------------------------------
# Tier 1: Subsystem XML parsing
# ---------------------------------------------------------------------------


def _parse_subsystem_xml(xml_path: Path) -> Tuple[str, List[str]]:
    """Parse a Subsystem.xml and return (subsystem_name, [content_items])."""
    subsystem_name = xml_path.parent.parent.name  # .../SubsystemName/Ext/Subsystem.xml

    items: List[str] = []
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        # Handle namespace prefixes — 1C XML uses various ns
        ns_map: Dict[str, str] = {}
        for event, elem in ET.iterparse(str(xml_path), events=["start-ns"]):
            prefix, uri = elem
            ns_map[prefix] = uri

        # Re-parse with awareness of found namespaces
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        # Find all Item elements regardless of namespace
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Item" and elem.text:
                items.append(elem.text.strip())
    except (ET.ParseError, OSError):
        pass

    return subsystem_name, items


def _build_subsystem_map(config_path: Path) -> Dict[str, str]:
    """Build mapping: metadata_object → subsystem_name from all Subsystem.xml files."""
    obj_to_subsystem: Dict[str, str] = {}

    subsystem_dir = config_path / "Subsystems"
    if not subsystem_dir.exists():
        return obj_to_subsystem

    for xml_path in subsystem_dir.rglob("Subsystem.xml"):
        subsystem_name, items = _parse_subsystem_xml(xml_path)
        for item in items:
            # item is like "Catalog.Номенклатура"
            if item not in obj_to_subsystem:
                obj_to_subsystem[item] = subsystem_name

    return obj_to_subsystem


# ---------------------------------------------------------------------------
# Tier 2: Keyword matching on filepath / object name
# ---------------------------------------------------------------------------


def _classify_by_keywords(
    module_path: str, metadata_obj: Optional[str]
) -> Optional[Tuple[str, float]]:
    """Match domain by keywords in path and object name. Returns (domain, confidence) or None."""
    text_to_match = module_path.lower()
    if metadata_obj:
        text_to_match += " " + metadata_obj.lower()

    best_domain: Optional[str] = None
    best_score = 0

    for domain, pattern in _DOMAIN_PATTERNS.items():
        hits = pattern.findall(text_to_match)
        if hits:
            score = len(hits)
            if score > best_score:
                best_score = score
                best_domain = domain

    if best_domain:
        confidence = min(0.9, 0.5 + 0.1 * best_score)
        return best_domain, confidence

    return None


# ---------------------------------------------------------------------------
# Tier 3: Content keyword scan
# ---------------------------------------------------------------------------

_ENCODINGS = ["utf-8-sig", "utf-8", "cp1251"]


def _read_bsl_content(path: Path) -> str:
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _classify_by_content(
    module_path: str,
    config_path: Path,
) -> Optional[Tuple[str, float]]:
    """Scan file content for domain keywords. Fallback tier."""
    full_path = config_path / module_path
    if not full_path.exists():
        return None

    try:
        content = _read_bsl_content(full_path).lower()
    except OSError:
        return None

    best_domain: Optional[str] = None
    best_score = 0

    for domain, pattern in _DOMAIN_PATTERNS.items():
        hits = pattern.findall(content)
        if hits:
            score = len(hits)
            if score > best_score:
                best_score = score
                best_domain = domain

    if best_domain and best_score >= 2:
        confidence = min(0.7, 0.3 + 0.05 * best_score)
        return best_domain, confidence

    return None


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------


def classify_module(
    module_path: str,
    subsystem_map: Dict[str, str],
    config_path: Path,
) -> Dict[str, Any]:
    """Classify a single module into a functional domain.

    Returns dict with: module_path, domain, confidence, method
    """
    metadata_obj = _extract_metadata_object(module_path)

    # Tier 1: Subsystem XML
    if metadata_obj and metadata_obj in subsystem_map:
        return {
            "module_path": module_path,
            "domain": subsystem_map[metadata_obj],
            "confidence": 1.0,
            "method": "subsystem_xml",
        }

    # Tier 2: Keyword matching on path/name
    kw_result = _classify_by_keywords(module_path, metadata_obj)
    if kw_result:
        return {
            "module_path": module_path,
            "domain": kw_result[0],
            "confidence": kw_result[1],
            "method": "keyword_path",
        }

    # Tier 3: Content scan — DISABLED (too slow for 26K+ files)
    # content_result = _classify_by_content(module_path, config_path)

    # Unclassified
    return {
        "module_path": module_path,
        "domain": "Прочее",
        "confidence": 0.0,
        "method": "none",
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_classification(
    config_path: Path,
    features_path: Path,
    output: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Classify all modules from features NDJSON into functional domains.

    Returns list of classification dicts and writes CSV.
    """
    config_path = config_path.resolve()

    # Load feature records
    records: List[Dict[str, Any]] = []
    with open(features_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Classifying {len(records)} modules…", file=sys.stderr)

    # Build subsystem map
    subsystem_map = _build_subsystem_map(config_path)
    print(
        f"  Subsystem map: {len(subsystem_map)} metadata objects mapped.",
        file=sys.stderr,
    )

    # First pass: classify by Tier 1 (subsystem) and Tier 2 (keywords)
    classified: List[Dict[str, Any]] = []
    unclassified_paths: List[str] = []
    for rec in records:
        module_path = rec["module_path"]
        result = classify_module(module_path, subsystem_map, config_path)
        if result["method"] != "none":
            classified.append(result)
        else:
            unclassified_paths.append(module_path)

    print(
        f"  After Tier 1+2: {len(classified)} classified, "
        f"{len(unclassified_paths)} remaining",
        file=sys.stderr,
    )

    # Second pass: Tier 3 content scan for unclassified modules (batch read)
    # Truncate to first 8 KB per file — domain keywords cluster in declarations
    _CONTENT_LIMIT = 8192
    if unclassified_paths:
        content_cache: Dict[str, str] = {}
        for mp in unclassified_paths:
            full_path = config_path / mp
            if full_path.exists():
                try:
                    content = _read_bsl_content(full_path)
                    if content:
                        content_cache[mp] = content[:_CONTENT_LIMIT].lower()
                except OSError:
                    pass

        print(
            f"  Tier 3: read {len(content_cache)} files for content scan",
            file=sys.stderr,
        )

        # Pre-compile simple substring check lists for fast pre-filter
        _domain_kw_lists = {
            domain: [kw.lower() for kw in keywords]
            for domain, keywords in DOMAIN_KEYWORDS.items()
        }

        tier3_hits = 0
        for mp in unclassified_paths:
            content = content_cache.get(mp)
            if not content:
                classified.append(
                    {
                        "module_path": mp,
                        "domain": "Прочее",
                        "confidence": 0.0,
                        "method": "none",
                    }
                )
                continue

            best_domain: Optional[str] = None
            best_score = 0
            for domain, kw_list in _domain_kw_lists.items():
                score = sum(1 for kw in kw_list if kw in content)
                if score > best_score:
                    best_score = score
                    best_domain = domain

            if best_domain and best_score >= 2:
                confidence = min(0.7, 0.3 + 0.05 * best_score)
                classified.append(
                    {
                        "module_path": mp,
                        "domain": best_domain,
                        "confidence": confidence,
                        "method": "content_scan",
                    }
                )
                tier3_hits += 1
            else:
                classified.append(
                    {
                        "module_path": mp,
                        "domain": "Прочее",
                        "confidence": 0.0,
                        "method": "none",
                    }
                )

        print(f"  Tier 3: classified {tier3_hits} more modules", file=sys.stderr)

    results = classified

    # Stats
    method_counts: Dict[str, int] = {}
    domain_counts: Dict[str, int] = {}
    for r in results:
        method_counts[r["method"]] = method_counts.get(r["method"], 0) + 1
        domain_counts[r["domain"]] = domain_counts.get(r["domain"], 0) + 1

    print(f"  By method: {method_counts}", file=sys.stderr)
    print(
        f"  By domain: {dict(sorted(domain_counts.items(), key=lambda x: -x[1]))}",
        file=sys.stderr,
    )

    # Write CSV
    out_stream = (
        open(output, "w", encoding="utf-8", newline="") if output else sys.stdout
    )
    try:
        writer = csv.DictWriter(
            out_stream, fieldnames=["module_path", "domain", "confidence", "method"]
        )
        writer.writeheader()
        writer.writerows(results)
    finally:
        if output:
            out_stream.close()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BSL domain classification")
    parser.add_argument("--config-path", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    run_classification(args.config_path, args.features, args.output)
