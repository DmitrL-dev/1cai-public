"""
1C XML Parser
-------------

Parses XML files exported from 1C:Enterprise Designer to extract metadata structure.
Populates the Unified Change Graph with metadata objects (Catalogs, Documents, etc.).
"""

import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from src.ai.code_analysis.graph import Edge, EdgeKind, Node, NodeKind

logger = logging.getLogger(__name__)


class OneCXMLParser:
    """
    Universal parser for 1C configuration XML exports.
    """

    # Mapping from XML root tag (or internal type) to NodeKind
    TAG_TO_KIND = {
        "Catalog": NodeKind.BSL_CATALOG,
        "Document": NodeKind.BSL_DOCUMENT,
        "Enum": NodeKind.BSL_ENUM,
        "Constant": NodeKind.BSL_CONSTANT,
        "InformationRegister": NodeKind.BSL_REGISTER_INFORMATION,
        "AccumulationRegister": NodeKind.BSL_REGISTER_ACCUMULATION,
        "AccountingRegister": NodeKind.BSL_REGISTER_ACCOUNTING,
        "CalculationRegister": NodeKind.BSL_REGISTER_CALCULATION,
        "Report": NodeKind.BSL_REPORT,
        "DataProcessor": NodeKind.BSL_DATA_PROCESSOR,
        "CommonModule": NodeKind.BSL_COMMON_MODULE,
        "Subsystem": NodeKind.BSL_SUBSYSTEM,
        "Role": NodeKind.BSL_ROLE,
        "CommonTemplate": NodeKind.BSL_COMMON_TEMPLATE,
        "CommonPicture": NodeKind.BSL_COMMON_PICTURE,
        "CommonCommand": NodeKind.BSL_COMMON_COMMAND,
        "CommonForm": NodeKind.BSL_COMMON_FORM,
        "FilterCriterion": NodeKind.BSL_FILTER_CRITERION,
        "EventSubscription": NodeKind.BSL_EVENT_SUBSCRIPTION,
        "ScheduledJob": NodeKind.BSL_SCHEDULED_JOB,
        "SessionParameter": NodeKind.BSL_SESSION_PARAMETER,
        "FunctionalOption": NodeKind.BSL_FUNCTIONAL_OPTION,
        "SettingsStorage": NodeKind.BSL_SETTINGS_STORAGE,
        "StyleItem": NodeKind.BSL_STYLE_ITEM,
        "Language": NodeKind.BSL_LANGUAGE,
        "WebService": NodeKind.BSL_WEB_SERVICE,
        "HTTPService": NodeKind.BSL_HTTP_SERVICE,
        "XDTOPackage": NodeKind.BSL_XDTO_PACKAGE,
        "ExchangePlan": NodeKind.BSL_EXCHANGE_PLAN,
        "ChartOfAccounts": NodeKind.BSL_CHART_OF_ACCOUNTS,
        "ChartOfCharacteristicTypes": NodeKind.BSL_CHART_OF_CHARACTERISTIC_TYPES,
        "ChartOfCalculationTypes": NodeKind.BSL_CHART_OF_CALCULATION_TYPES,
        "BusinessProcess": NodeKind.BSL_BUSINESS_PROCESS,
        "Task": NodeKind.BSL_TASK,
    }

    def parse_directory(self, dir_path: str) -> List[Node]:
        """
        Recursively parse all XML files in a directory.
        """
        nodes = []
        if not os.path.exists(dir_path):
            logger.warning(f"Directory not found: {dir_path}")
            return []

        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(".xml"):
                    file_path = os.path.join(root, file)
                    try:
                        file_nodes = self.parse_file(file_path)
                        nodes.extend(file_nodes)
                    except Exception as e:
                        logger.error(f"Failed to parse {file_path}: {e}")
        return nodes

    def parse_file(self, file_path: str) -> List[Node]:
        """
        Parse a single XML file and return extracted nodes.
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.error(f"XML Parse Error in {file_path}: {e}")
            return []

        # Remove namespace for easier tag matching
        # (Naive approach, but sufficient for standard 1C exports)
        self._strip_namespace(root)

        nodes = []

        # Check if it's a MetaDataObject container
        if root.tag == "MetaDataObject":
            # Usually contains one child which is the actual object
            for child in root:
                node = self._parse_object(child, file_path)
                if node:
                    nodes.append(node)
        else:
            # Try to parse root directly
            node = self._parse_object(root, file_path)
            if node:
                nodes.append(node)

        return nodes

    def _parse_object(self, element: ET.Element, file_path: str) -> Optional[Node]:
        """
        Parse a specific XML element into a Node.
        """
        tag = element.tag
        kind = self.TAG_TO_KIND.get(tag, NodeKind.BSL_METADATA_OBJECT)

        # Extract basic properties
        props = self._extract_properties(element)
        name = props.get("Name", "Unknown")

        # Generate ID (using Name as stable identifier for now, or UUID if present)
        uuid = props.get("Uuid")
        node_id = f"{kind.value}:{name}" if name != "Unknown" else f"{kind.value}:{uuid}"

        # Extract nested collections
        attributes = self._extract_collection(element, "Attributes", "Attribute")
        tabular_sections = self._extract_collection(element, "TabularSections", "TabularSection")
        forms = self._extract_collection(element, "Forms", "Form")
        templates = self._extract_collection(element, "Templates", "Template")
        commands = self._extract_collection(element, "Commands", "Command")

        props["attributes"] = attributes
        props["tabular_sections"] = tabular_sections
        props["forms"] = forms
        props["templates"] = templates
        props["commands"] = commands
        props["file_path"] = file_path

        return Node(id=node_id, kind=kind, display_name=name, labels=[tag], props=props)

    def _extract_properties(self, element: ET.Element) -> Dict[str, Any]:
        """Extract standard properties like Name, Synonym, Comment, Uuid."""
        props = {}

        # Direct attributes of the XML element
        if "uuid" in element.attrib:
            props["Uuid"] = element.attrib["uuid"]

        # Child elements
        for child in element:
            if child.tag == "Properties":
                # Deep dive into Properties bag
                for prop in child:
                    # Handle simple text values
                    if len(prop) == 0:
                        props[prop.tag] = prop.text
                    # Handle Synonym (v8:item)
                    elif prop.tag == "Synonym":
                        # Extract ru/en values
                        # Since namespaces are stripped, we look for 'item', 'lang', 'content' directly
                        for item in prop.findall(".//item"):
                            lang = item.find("lang")
                            content = item.find("content")
                            if lang is not None and content is not None:
                                props[f"Synonym_{lang.text}"] = content.text
                    elif prop.tag == "Content":
                        # Extract list of items (e.g. for Subsystems)
                        items = []
                        for item in prop.findall("Item"):
                            if item.text:
                                items.append(item.text)
                        props["Content"] = items
            elif not list(child):  # Simple child
                props[child.tag] = child.text
        return props

    def _extract_collection(self, element: ET.Element, collection_tag: str, item_tag: str) -> List[Dict[str, Any]]:
        """Extract a list of items from a child collection element."""
        items = []

        # 1. Try ChildObjects container (standard 1C structure)
        child_objects = element.find("ChildObjects")
        if child_objects is not None:
            # Items are usually direct children of ChildObjects
            for item in child_objects.findall(item_tag):
                items.append(self._extract_properties(item))

            if items:
                return items

        # 2. Try specific container tag (fallback or for specific structures)
        container = element.find(collection_tag)
        if container is not None:
            for item in container.findall(item_tag):
                items.append(self._extract_properties(item))

        return items

    def _strip_namespace(self, element: ET.Element):
        """Remove namespace from element tags in-place."""
        if element.tag.startswith("{"):
            element.tag = element.tag.split("}", 1)[1]
        for child in element:
            self._strip_namespace(child)
