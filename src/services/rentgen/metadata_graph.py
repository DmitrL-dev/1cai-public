"""Read-only EDT metadata graph for 1C configurations."""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any
import re
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "data" / "configs" / "unpacked"

FOLDER_TO_TYPE: dict[str, str] = {
    "Catalogs": "Catalog",
    "Documents": "Document",
    "InformationRegisters": "InformationRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "AccountingRegisters": "AccountingRegister",
    "CalculationRegisters": "CalculationRegister",
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
    "IntegrationServices": "IntegrationService",
    "WSReferences": "WSReference",
    "XDTOPackages": "XDTOPackage",
}

_REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-zА-Яа-яЁё0-9_]+)+$")
_DANGEROUS_RIGHTS = {
    "Delete",
    "InteractiveDelete",
    "Update",
    "Edit",
    "Administration",
    "InteractiveMarkForDeletion",
    "InteractiveClearDeletionMark",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _direct_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in list(element):
        if _local(child.tag) == name:
            return child
    return None


def _first_text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = _direct_child(element, name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _localized_text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = _direct_child(element, name)
    if child is None:
        return None

    by_lang: dict[str, str] = {}
    direct = child.text.strip() if child.text else ""
    for item in child.iter():
        if _local(item.tag) != "item":
            continue
        lang = ""
        content = ""
        for part in item.iter():
            local = _local(part.tag)
            if local == "lang" and part.text:
                lang = part.text.strip()
            elif local == "content" and part.text:
                content = part.text.strip()
        if content:
            by_lang[lang or ""] = content

    return by_lang.get("ru") or by_lang.get("") or next(iter(by_lang.values()), None) or direct or None


def _safe_parse(path: Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None


def _metadata_child(root: ET.Element | None) -> ET.Element | None:
    if root is None:
        return None
    if _local(root.tag) != "MetaDataObject":
        return root
    for child in list(root):
        if _local(child.tag) not in {"InternalInfo", "Properties"}:
            return child
    return None


def _properties(meta: ET.Element | None) -> ET.Element | None:
    return _direct_child(meta, "Properties") if meta is not None else None


def _nested_text(element: ET.Element | None, name: str) -> str | None:
    """Text of a direct <name> child, or of <name> under a direct <Properties>
    child. EDT stores attribute/dimension/resource fields under <Properties>,
    not as direct children, so the direct-only lookup misses everything."""
    return _first_text(element, name) or _first_text(_properties(element), name)


def _nested_localized(element: ET.Element | None, name: str) -> str | None:
    return _localized_text(element, name) or _localized_text(_properties(element), name)


def _xml_path_for_object(folder: Path, object_name: str) -> Path | None:
    direct = folder / f"{object_name}.xml"
    if direct.exists():
        return direct
    nested = folder / object_name / f"{object_name}.xml"
    if nested.exists():
        return nested
    return None


def _object_dir_for_xml(folder: Path, object_name: str) -> Path:
    return folder / object_name


def _module_type(path: Path) -> str:
    name = path.name.lower()
    parts = [part.lower() for part in path.parts]
    if "forms" in parts:
        return "FormModule"
    if name == "objectmodule.bsl":
        return "ObjectModule"
    if name == "managermodule.bsl":
        return "ManagerModule"
    if name == "module.bsl":
        return "Module"
    if name == "commandmodule.bsl":
        return "CommandModule"
    return "BSLModule"


def _modules(config_path: Path, object_dir: Path) -> list[dict[str, Any]]:
    if not object_dir.exists():
        return []
    modules = []
    for path in sorted(object_dir.rglob("*.bsl")):
        try:
            rel = path.relative_to(config_path).as_posix()
        except ValueError:
            rel = path.as_posix()
        modules.append(
            {
                "path": rel,
                "name": path.stem,
                "type": _module_type(path),
                "size": path.stat().st_size if path.exists() else 0,
            }
        )
    return modules


def _forms(config_path: Path, object_dir: Path) -> list[dict[str, Any]]:
    forms_dir = object_dir / "Forms"
    if not forms_dir.exists():
        return []

    forms = []
    for xml_path in sorted(forms_dir.glob("*.xml")):
        root = _safe_parse(xml_path)
        meta = _metadata_child(root)
        props = _properties(meta)
        form_dir = forms_dir / xml_path.stem
        module = form_dir / "Ext" / "Form" / "Module.bsl"
        forms.append(
            {
                "name": _first_text(props, "Name") or xml_path.stem,
                "synonym": _localized_text(props, "Synonym"),
                "form_type": _first_text(props, "FormType"),
                "path": xml_path.relative_to(config_path).as_posix(),
                "module_path": module.relative_to(config_path).as_posix() if module.exists() else None,
            }
        )
    return forms


def _commands(config_path: Path, object_dir: Path) -> list[dict[str, Any]]:
    commands_dir = object_dir / "Commands"
    if not commands_dir.exists():
        return []
    return [
        {"name": path.stem, "path": path.relative_to(config_path).as_posix()}
        for path in sorted(commands_dir.glob("*.xml"))
    ]


def _asset_key(config_path: Path, path: Path) -> tuple[str, str] | None:
    try:
        parts = path.relative_to(config_path).parts
    except ValueError:
        return None
    if len(parts) < 2 or parts[0] not in FOLDER_TO_TYPE:
        return None
    return (parts[0], parts[1])


def _collect_assets(config_path: Path) -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    modules: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    forms: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    commands: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for path in sorted(config_path.rglob("*.bsl")):
        key = _asset_key(config_path, path)
        if key is None:
            continue
        rel = path.relative_to(config_path).as_posix()
        modules[key].append(
            {
                "path": rel,
                "name": path.stem,
                "type": _module_type(path),
                "size": path.stat().st_size if path.exists() else 0,
            }
        )

    for path in sorted(config_path.glob("*/*/Forms/*.xml")):
        key = _asset_key(config_path, path)
        if key is None:
            continue
        form_dir = path.parent / path.stem
        module = form_dir / "Ext" / "Form" / "Module.bsl"
        forms[key].append(
            {
                "name": path.stem,
                "synonym": None,
                "form_type": None,
                "path": path.relative_to(config_path).as_posix(),
                "module_path": module.relative_to(config_path).as_posix() if module.exists() else None,
            }
        )

    for path in sorted(config_path.glob("*/*/Commands/*.xml")):
        key = _asset_key(config_path, path)
        if key is None:
            continue
        commands[key].append({"name": path.stem, "path": path.relative_to(config_path).as_posix()})

    return {"modules": dict(modules), "forms": dict(forms), "commands": dict(commands)}


def _attribute_name(element: ET.Element) -> str | None:
    attr_name = element.attrib.get("name")
    if attr_name:
        return attr_name
    # Old format: a direct <Name> child. EDT format: <Properties><Name>.
    return _nested_text(element, "Name")


def _attributes(meta: ET.Element | None, limit: int = 60) -> list[dict[str, str]]:
    if meta is None:
        return []
    attrs: list[dict[str, str]] = []
    for element in meta.iter():
        if _local(element.tag) != "Attribute":
            continue
        name = _attribute_name(element)
        if not name:
            continue
        attrs.append(
            {
                "name": name,
                "synonym": _nested_localized(element, "Synonym") or "",
                "fill_checking": _nested_text(element, "FillChecking") or "",
            }
        )
        if len(attrs) >= limit:
            break
    return attrs


def _tabular_sections(meta: ET.Element | None, limit: int = 40) -> list[dict[str, str]]:
    if meta is None:
        return []
    sections: list[dict[str, str]] = []
    for element in meta.iter():
        if _local(element.tag) != "TabularSection":
            continue
        name = _attribute_name(element)
        if not name:
            continue
        sections.append({"name": name, "synonym": _nested_localized(element, "Synonym") or ""})
        if len(sections) >= limit:
            break
    return sections


def _named_items(meta: ET.Element | None, tag_name: str, limit: int = 80) -> list[dict[str, str]]:
    if meta is None:
        return []
    items: list[dict[str, str]] = []
    for element in meta.iter():
        if _local(element.tag) != tag_name:
            continue
        name = _attribute_name(element)
        if not name:
            continue
        items.append(
            {
                "name": name,
                "synonym": _nested_localized(element, "Synonym") or "",
                "type": _nested_text(element, "Type") or "",
            }
        )
        if len(items) >= limit:
            break
    return items


def _references(meta: ET.Element | None, own_ref: str, limit: int = 80) -> list[str]:
    if meta is None:
        return []
    refs: list[str] = []
    for element in meta.iter():
        value = (element.text or "").strip()
        if value and value != own_ref and _REF_RE.match(value):
            refs.append(value)
    return list(dict.fromkeys(refs))[:limit]


def _rights(config_path: Path, object_dir: Path) -> dict[str, Any] | None:
    rights_path = object_dir / "Ext" / "Rights.xml"
    if not rights_path.exists():
        return None
    root = _safe_parse(rights_path)
    if root is None:
        return {
            "path": rights_path.relative_to(config_path).as_posix(),
            "objects": 0,
            "rights": 0,
            "dangerous": [],
        }

    object_count = 0
    right_count = 0
    dangerous_total = 0
    dangerous: list[dict[str, str]] = []
    by_right: Counter[str] = Counter()
    for object_element in root.iter():
        if _local(object_element.tag) != "object":
            continue
        object_count += 1
        object_name = _first_text(object_element, "name") or ""
        for right in object_element:
            if _local(right.tag) != "right":
                continue
            right_name = _first_text(right, "name") or ""
            value = (_first_text(right, "value") or "").lower()
            if value == "true":
                right_count += 1
                by_right[right_name] += 1
                if right_name in _DANGEROUS_RIGHTS:
                    dangerous_total += 1
                    if len(dangerous) < 30:
                        dangerous.append({"object": object_name, "right": right_name})

    return {
        "path": rights_path.relative_to(config_path).as_posix(),
        "objects": object_count,
        "rights": right_count,
        "dangerous_total": dangerous_total,
        "dangerous": dangerous,
        "by_right": dict(by_right),
    }


def _rights_path(config_path: Path, object_dir: Path) -> str | None:
    rights_path = object_dir / "Ext" / "Rights.xml"
    if not rights_path.exists():
        return None
    return rights_path.relative_to(config_path).as_posix()


def _configuration_info(config_path: Path) -> dict[str, str | None]:
    xml_path = config_path / "Configuration.xml"
    root = _safe_parse(xml_path)
    meta = _metadata_child(root)
    props = _properties(meta)
    return {
        "name": _first_text(props, "Name"),
        "synonym": _localized_text(props, "Synonym"),
        "version": _first_text(props, "Version"),
        "vendor": _first_text(props, "Vendor"),
        "path": xml_path.relative_to(config_path).as_posix() if xml_path.exists() else None,
    }


@lru_cache(maxsize=4)
def build_metadata_graph(config_path_raw: str | None = None) -> dict[str, Any]:
    config_path = Path(config_path_raw) if config_path_raw else DEFAULT_CONFIG_PATH
    config_path = config_path.resolve()
    if not config_path.exists():
        return {
            "available": False,
            "config_path": str(config_path),
            "configuration": {},
            "objects": [],
            "summary": {"total_objects": 0},
        }

    assets = _collect_assets(config_path)
    objects: list[dict[str, Any]] = []
    for folder_name, metadata_type in FOLDER_TO_TYPE.items():
        folder = config_path / folder_name
        if not folder.exists():
            continue
        for xml_path in sorted(folder.glob("*.xml")):
            object_name = xml_path.stem
            object_dir = _object_dir_for_xml(folder, object_name)
            rel_path = xml_path.relative_to(config_path).as_posix()
            ref = f"{metadata_type}.{object_name}"
            key = (folder_name, object_name)
            forms = assets["forms"].get(key, [])
            modules = assets["modules"].get(key, [])
            commands = assets["commands"].get(key, [])
            rights_path = _rights_path(config_path, object_dir)

            objects.append(
                {
                    "type": metadata_type,
                    "name": object_name,
                    "synonym": None,
                    "comment": None,
                    "uuid": None,
                    "ref": ref,
                    "path": rel_path,
                    "folder": folder_name,
                    "modules": modules,
                    "forms": forms,
                    "commands": commands,
                    "attributes": [],
                    "tabular_sections": [],
                    "dimensions": [],
                    "resources": [],
                    "references": [],
                    "rights": None,
                    "rights_path": rights_path,
                    "counts": {
                        "modules": len(modules),
                        "forms": len(forms),
                        "commands": len(commands),
                        "attributes": 0,
                        "tabular_sections": 0,
                        "dimensions": 0,
                        "resources": 0,
                        "rights_objects": 0,
                        "rights": 0,
                        "has_rights": 1 if rights_path else 0,
                    },
                }
            )

    by_type = Counter(obj["type"] for obj in objects)
    total_forms = sum(obj["counts"]["forms"] for obj in objects)
    total_modules = sum(obj["counts"]["modules"] for obj in objects)
    total_rights = sum(obj["counts"]["rights"] for obj in objects)
    roles_with_rights_xml = sum(1 for obj in objects if obj["counts"].get("has_rights"))
    summary = {
        "total_objects": len(objects),
        "by_type": dict(by_type),
        "total_forms": total_forms,
        "total_modules": total_modules,
        "total_roles": by_type.get("Role", 0),
        "total_rights": total_rights,
        "roles_with_dangerous_rights": 0,
        "roles_with_rights_xml": roles_with_rights_xml,
    }

    return {
        "available": True,
        "config_path": str(config_path),
        "configuration": _configuration_info(config_path),
        "summary": summary,
        "objects": objects,
    }


def metadata_summary(config_path: str | None = None) -> dict[str, Any]:
    graph = build_metadata_graph(config_path)
    return {
        "available": graph["available"],
        "config_path": graph["config_path"],
        "configuration": graph["configuration"],
        "summary": graph["summary"],
    }


def search_metadata(
    query: str | None = None,
    *,
    metadata_type: str | None = None,
    limit: int = 30,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    graph = build_metadata_graph(config_path)
    needle = (query or "").casefold()
    metadata_type_cf = metadata_type.casefold() if metadata_type else None
    results = []

    for obj in graph["objects"]:
        if metadata_type_cf and obj["type"].casefold() != metadata_type_cf:
            continue
        haystack = " ".join(
            str(part or "")
            for part in (obj["name"], obj["synonym"], obj["ref"], obj["path"], obj["type"])
        ).casefold()
        if needle and needle not in haystack:
            continue
        results.append(_preview(obj))
        if len(results) >= limit:
            break
    return results


def get_metadata_object(identifier: str, config_path: str | None = None) -> dict[str, Any] | None:
    graph = build_metadata_graph(config_path)
    needle = identifier.casefold().replace("\\", "/")
    for obj in graph["objects"]:
        candidates = {
            obj["ref"].casefold(),
            obj["path"].casefold(),
            obj["name"].casefold(),
            f'{obj["type"]}.{obj["name"]}'.casefold(),
        }
        if needle in candidates:
            return _enrich_object(graph, obj)
    return None


def _enrich_object(graph: dict[str, Any], obj: dict[str, Any]) -> dict[str, Any]:
    config_path = Path(graph["config_path"])
    xml_path = config_path / obj["path"]
    root = _safe_parse(xml_path)
    meta = _metadata_child(root)
    props = _properties(meta)
    enriched = dict(obj)
    object_name = Path(obj["path"]).stem
    object_dir = config_path / obj["folder"] / object_name

    attrs = _attributes(meta)
    tabular_sections = _tabular_sections(meta)
    dimensions = _named_items(meta, "Dimension")
    resources = _named_items(meta, "Resource")
    rights = _rights(config_path, object_dir)

    enriched["name"] = _first_text(props, "Name") or obj["name"]
    enriched["synonym"] = _localized_text(props, "Synonym")
    enriched["comment"] = _first_text(props, "Comment")
    enriched["uuid"] = meta.attrib.get("uuid") if meta is not None else obj.get("uuid")
    enriched["attributes"] = attrs
    enriched["tabular_sections"] = tabular_sections
    enriched["dimensions"] = dimensions
    enriched["resources"] = resources
    enriched["references"] = _references(meta, obj["ref"])
    enriched["rights"] = rights
    enriched["counts"] = dict(obj["counts"])
    enriched["counts"].update(
        {
            "attributes": len(attrs),
            "tabular_sections": len(tabular_sections),
            "dimensions": len(dimensions),
            "resources": len(resources),
            "rights_objects": rights["objects"] if rights else 0,
            "rights": rights["rights"] if rights else 0,
        }
    )
    return enriched


def _preview(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": obj["type"],
        "name": obj["name"],
        "synonym": obj["synonym"],
        "ref": obj["ref"],
        "path": obj["path"],
        "uuid": obj["uuid"],
        "counts": obj["counts"],
    }
