"""Closed host-side source-fact observations; no name binding or native claims."""
import json
import re

from .errors import CoreError
from .metadata_xml import parse_xml
from .source_fact_process import failure

LEX_REASONS = frozenset("""invalid_utf8 invalid_bom forbidden_control invalid_line_ending
unsupported_code_character identifier_limit token_bytes_limit token_count_limit
invalid_number unsupported_literal unterminated_string multiline_string
unsupported_keyword unsupported_top_level invalid_header duplicate_parameter
parameter_limit duplicate_routine routine_limit nested_routine mismatched_terminator
missing_terminator stray_structural_keyword unbalanced_delimiter delimiter_depth_limit""".split())
SELECTOR_REASONS = frozenset("""caller_not_admitted selector_span_invalid
selector_not_qualified selector_outside_body selector_chained""".split())
HEADER_REASONS = frozenset({"selector_unavailable", "candidate_not_admitted", "declaration_unavailable"})
IDENT = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]{0,127}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
UINT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
_LOWER = "abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
_CASE = str.maketrans(_UPPER, _LOWER)
_N = "{http://v8.1c.ru/8.3/MDClasses}"
_WS = " \t\r\n"
_ID_PATTERN = r"[A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]*"
_HEADER = re.compile(r"(?P<kind>procedure|function|процедура|функция)[ \t]+(?P<name>"
                     + _ID_PATTERN + r")[ \t]*\((?P<params>[^()]*)\)(?:[ \t]*(?P<export>export|экспорт))?\Z")
_PARAM = re.compile(r"(?:(?:val|знач)[ \t]+)?(?P<name>" + _ID_PATTERN + r")\Z")
_RESERVED = frozenset(word.translate(_CASE) for word in """
Procedure Процедура Function Функция EndProcedure КонецПроцедуры EndFunction КонецФункции
Export Экспорт Val Знач If Если Then Тогда ElsIf ИначеЕсли Else Иначе EndIf КонецЕсли ElseIf
For Для Each Каждого In Из To По While Пока Do Цикл EndDo КонецЦикла Return Возврат
Continue Продолжить Break Прервать Var Перем And И Or Или Not Не New Новый Goto Перейти
True Истина False Ложь Undefined Неопределено Null Try Попытка Except Исключение
EndTry КонецПопытки Raise ВызватьИсключение AddHandler ДобавитьОбработчик
RemoveHandler УдалитьОбработчик Execute Выполнить Eval Вычислить Async Асинх Await Ждать
""".split())


def unavailable(reason):
    return {"state": "unavailable", "reason": reason}


def identifier(value):
    return type(value) is str and IDENT.fullmatch(value) is not None and len(value.encode("utf-8")) <= 512


def equal_identifier(a, b):
    return identifier(a) and identifier(b) and a.translate(_CASE) == b.translate(_CASE)


def fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise failure("PROTOCOL_INVALID")
    return value


def uint(value, maximum=2_147_483_647, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise failure("PROTOCOL_INVALID")
    return value


def strict_json(raw, limit=65_536):
    if type(raw) is not bytes or not 1 <= len(raw) <= limit or not raw.startswith(b"{") or not raw.endswith(b"}"):
        raise failure("PROTOCOL_INVALID")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise failure("PROTOCOL_INVALID")
            result[key] = value
        return result

    def number(value):
        if UINT.fullmatch(value) is None or len(value) > 10:
            raise failure("PROTOCOL_INVALID")
        return uint(int(value))

    def reject(_):
        raise failure("PROTOCOL_INVALID")

    def walk(value, depth=0):
        if type(value) is dict:
            if depth >= 12:
                raise failure("PROTOCOL_INVALID")
            for key, item in value.items():
                key.encode("utf-8", "strict")
                walk(item, depth + 1)
        elif type(value) is str:
            value.encode("utf-8", "strict")
        elif value is not None and type(value) not in (bool, int):
            raise failure("PROTOCOL_INVALID")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_int=number, parse_float=reject, parse_constant=reject)
        walk(value)
        return value
    except (UnicodeError, ValueError, RecursionError):
        raise failure("PROTOCOL_INVALID") from None


def xml_observations(raw):
    """Return an internal Name and explicit Server observation from selected bytes.

    This intentionally handwritten shape does not admit real Designer's version/
    UUID attributes or claim configuration membership/serialization qualification.
    """
    if raw is None:
        return None, unavailable("xml_missing")
    try:
        root = parse_xml(raw)
    except CoreError as error:
        reason = {"METADATA_LIMIT_EXCEEDED": "xml_limit", "XML_FORBIDDEN": "xml_forbidden"}.get(error.code, "xml_invalid")
        return None, unavailable(reason)

    def white(text):
        return text is None or not text.strip(_WS)

    def container(node, tag, child_tags):
        return (node.tag == _N + tag and not node.attrib and white(node.text)
                and white(node.tail) and all(child.tag in {_N + v for v in child_tags}
                                            and white(child.tail) for child in node))

    if not container(root, "MetaDataObject", {"CommonModule"}):
        return None, unavailable("xml_shape_unsupported")
    modules = list(root)
    if any(not container(module, "CommonModule", {"Properties"}) for module in modules):
        return None, unavailable("xml_shape_unsupported")
    property_sets = [props for module in modules for props in module]
    if any(not container(props, "Properties", {"Name", "Server"}) for props in property_sets):
        return None, unavailable("xml_shape_unsupported")
    if len(modules) > 1 or any(len(module) > 1 for module in modules):
        return None, unavailable("xml_duplicate_container")
    if len(modules) != 1 or len(property_sets) != 1:
        return None, unavailable("xml_shape_unsupported")
    props = property_sets[0]
    names = [p for p in props if p.tag == _N + "Name"]
    if not names:
        return None, unavailable("xml_name_missing")
    if len(names) != 1:
        return None, unavailable("xml_name_duplicate")
    name_node = names[0]
    name = (name_node.text or "").strip(_WS)
    if name_node.attrib or len(name_node) or not identifier(name):
        return None, unavailable("xml_name_invalid")
    servers = [p for p in props if p.tag == _N + "Server"]
    if not servers:
        return name, unavailable("xml_server_missing")
    if len(servers) != 1:
        return name, unavailable("xml_server_duplicate")
    server = servers[0]
    value = (server.text or "").strip(_WS)
    if server.attrib or len(server) or value not in {"true", "false"}:
        return name, unavailable("xml_server_invalid")
    return name, {"state": "observed", "value": value == "true"}


def _span(value, raw):
    fields(value, ("start", "end"))
    start, end = uint(value["start"], len(raw)), uint(value["end"], len(raw))
    if start >= end or (start < len(raw) and raw[start] & 0xC0 == 0x80) or (end < len(raw) and raw[end] & 0xC0 == 0x80):
        raise failure("RECEIPT_INVALID")
    return start, end


def _inside(inner, outer):
    if not outer[0] <= inner[0] < inner[1] <= outer[1]:
        raise failure("RECEIPT_INVALID")


def _name_at(span, raw):
    start, end = _span(span, raw)
    try:
        name = raw[start:end].decode("utf-8")
    except UnicodeError:
        raise failure("RECEIPT_INVALID") from None
    if not identifier(name):
        raise failure("RECEIPT_INVALID")
    return name


def _validate_header_extent(header, source):
    """Cross-check the complete returned header line, never routine bodies.

    A clipped ')' before Export, or an Export token hidden in a comment, cannot
    become a validated receipt merely because its byte span is in bounds.
    """
    start, end = _span(header["header_span"], source)
    try:
        text = source[start:end].decode("utf-8")
    except UnicodeError:
        raise failure("RECEIPT_INVALID") from None
    match = _HEADER.fullmatch(text.translate(_CASE))
    if match is None:
        raise failure("RECEIPT_INVALID")
    name = match.group("name")
    if not identifier(name) or name in _RESERVED:
        raise failure("RECEIPT_INVALID")
    params = match.group("params").strip(" \t")
    seen = set()
    if params:
        items = params.split(",")
        if len(items) > 128:
            raise failure("RECEIPT_INVALID")
        for item in items:
            parameter = _PARAM.fullmatch(item.strip(" \t"))
            if parameter is None:
                raise failure("RECEIPT_INVALID")
            value = parameter.group("name")
            if not identifier(value) or value in _RESERVED or value in seen:
                raise failure("RECEIPT_INVALID")
            seen.add(value)

    def span(group):
        left, right = match.span(group)
        return start + len(text[:left].encode("utf-8")), start + len(text[:right].encode("utf-8"))

    if _span(header["name_span"], source) != span("name"):
        raise failure("RECEIPT_INVALID")
    observed_export = match.group("export") is not None
    if header["export"] is not observed_export:
        raise failure("RECEIPT_INVALID")
    if observed_export:
        if _span(header["export_span"], source) != span("export"):
            raise failure("RECEIPT_INVALID")
    elif header["export_span"] is not None:
        raise failure("RECEIPT_INVALID")
    line_end = min((p for p in (source.find(b"\r", end), source.find(b"\n", end)) if p >= 0), default=len(source))
    suffix = source[end:line_end].lstrip(b" \t")
    if suffix and not suffix.startswith(b"//"):
        raise failure("RECEIPT_INVALID")


def validate_scan(raw_response, caller, candidate, buffers, selection):
    """Validate only fixed-role receipts, not a second independent BSL compiler."""
    value = strict_json(raw_response)
    fields(value, ("protocol", "status", "caller", "candidate", "selector", "header"))
    if value["protocol"] != "source_fact_scan_v1" or value["status"] != "ok":
        raise failure("PROTOCOL_INVALID")
    for role, entry in (("caller", caller), ("candidate", candidate)):
        record = fields(value[role], ("entry_id", "size_bytes", "raw_sha256", "admission"))
        if (uint(record["entry_id"], 4095) != entry["entry_id"]
                or uint(record["size_bytes"], 524_288) != entry["size_bytes"]
                or record["raw_sha256"] != entry["raw_sha256"]):
            raise failure("RECEIPT_INVALID")
        admission = record["admission"]
        if type(admission) is not dict:
            raise failure("PROTOCOL_INVALID")
        if admission.get("state") == "admitted":
            fields(admission, ("state",))
        else:
            fields(admission, ("state", "reason"))
            if admission["state"] != "unavailable" or type(admission["reason"]) is not str or admission["reason"] not in LEX_REASONS:
                raise failure("PROTOCOL_INVALID")
    if caller["entry_id"] == candidate["entry_id"] and value["caller"] != value["candidate"]:
        raise failure("RECEIPT_INVALID")
    selector, header = value["selector"], value["header"]
    if type(selector) is not dict or type(header) is not dict:
        raise failure("PROTOCOL_INVALID")
    caller_admitted = value["caller"]["admission"]["state"] == "admitted"
    candidate_admitted = value["candidate"]["admission"]["state"] == "admitted"
    if selector.get("state") == "observed":
        fields(selector, ("state", "entry_id", "routine_span", "selector_span", "receiver_span", "method_span"))
        if not caller_admitted or uint(selector["entry_id"], 4095) != caller["entry_id"] or selector["selector_span"] != selection:
            raise failure("RECEIPT_INVALID")
        source = buffers[caller["entry_id"]]
        routine = _span(selector["routine_span"], source)
        chosen = _span(selector["selector_span"], source)
        receiver = _span(selector["receiver_span"], source)
        method = _span(selector["method_span"], source)
        _inside(chosen, routine)
        _inside(receiver, chosen)
        _inside(method, chosen)
        if receiver[0] != chosen[0] or method[1] != chosen[1] or receiver[1] >= method[0]:
            raise failure("RECEIPT_INVALID")
        between = source[receiver[1]:method[0]]
        if between.strip(b" \t") != b".":
            raise failure("RECEIPT_INVALID")
        receiver_name = _name_at(selector["receiver_span"], source)
        method_name = _name_at(selector["method_span"], source)
    else:
        fields(selector, ("state", "reason"))
        if selector["state"] != "unavailable" or type(selector["reason"]) is not str or selector["reason"] not in SELECTOR_REASONS:
            raise failure("PROTOCOL_INVALID")
        if (selector["reason"] == "caller_not_admitted") == caller_admitted:
            raise failure("RECEIPT_INVALID")
        receiver_name = method_name = None
    if header.get("state") == "observed":
        fields(header, ("state", "entry_id", "routine_span", "header_span", "name_span", "export", "export_span"))
        if selector["state"] != "observed" or not candidate_admitted or uint(header["entry_id"], 4095) != candidate["entry_id"] or type(header["export"]) is not bool:
            raise failure("RECEIPT_INVALID")
        source = buffers[candidate["entry_id"]]
        routine = _span(header["routine_span"], source)
        extent = _span(header["header_span"], source)
        name = _span(header["name_span"], source)
        _inside(extent, routine)
        _inside(name, extent)
        if extent[0] != routine[0] or not equal_identifier(_name_at(header["name_span"], source), method_name):
            raise failure("RECEIPT_INVALID")
        _validate_header_extent(header, source)
    else:
        fields(header, ("state", "reason"))
        if header["state"] != "unavailable" or type(header["reason"]) is not str or header["reason"] not in HEADER_REASONS:
            raise failure("PROTOCOL_INVALID")
        expected = "selector_unavailable" if selector["state"] != "observed" else "candidate_not_admitted" if not candidate_admitted else "declaration_unavailable"
        if header["reason"] != expected:
            raise failure("RECEIPT_INVALID")
    return value, receiver_name


def make_kernel_envelope(scan, receiver_name, candidate_name, xml_name, server,
                         *, caller, candidate, metadata):
    """Create invocation-local assertions; IDs do not authenticate provenance."""
    scope = {"case_id": 1, "input_id": 1, "selector_id": 1,
             "caller_entry_id": caller["entry_id"] + 1,
             "candidate_entry_id": candidate["entry_id"] + 1,
             "xml_entry_id": None if metadata is None else metadata["entry_id"] + 1}
    receipts = {"selector": None, "export": None, "server": None}
    base = {"case_id": 1, "input_id": 1, "selector_id": 1}
    if scan["selector"]["state"] != "observed":
        reason = scan["selector"]["reason"]
        if reason == "caller_not_admitted":
            reason = scan["caller"]["admission"]["reason"]
        observations = {"selector": unavailable(reason),
                        "export": unavailable("selector_unavailable"),
                        "server": unavailable("selector_unavailable")}
    else:
        observations = {"selector": {"state": "observed", "value": "qualified_selector", "receipt_id": 1}}
        receipts["selector"] = {"receipt_id": 1, **base, "entry_id": scope["caller_entry_id"]}
        if xml_name is None:
            observations.update(export=unavailable("candidate_identity_unavailable"), server=server)
        elif not equal_identifier(receiver_name, candidate_name) or not equal_identifier(receiver_name, xml_name):
            observations.update(export=unavailable("candidate_name_mismatch"), server=unavailable("candidate_name_mismatch"))
        else:
            header = scan["header"]
            observations["export"] = ({"state": "observed", "value": header["export"], "receipt_id": 2, "header_id": 1}
                                      if header["state"] == "observed" else unavailable(header["reason"]))
            observations["server"] = dict(server)
            if header["state"] == "observed":
                receipts["export"] = {"receipt_id": 2, **base, "entry_id": scope["candidate_entry_id"], "header_id": 1}
            if server["state"] == "observed":
                observations["server"].update(receipt_id=3, property_id=1)
                receipts["server"] = {"receipt_id": 3, **base, "entry_id": scope["xml_entry_id"], "property_id": 1}
    return {"schema_version": 2, "profile": "submitted_source_facts_v1",
            "rule_set": "source_observations_v1", "scope": scope,
            "observations": observations, "receipts": receipts,
            "receiver_binding": "unknown", "runtime_relation": "unknown"}


def validate_kernel(raw, submitted):
    value = strict_json(raw)
    expected = {"schema_version": 2, "profile": "submitted_source_facts_v1",
                "rule_set": "source_observations_v1",
                "assurance": "source_facts_host_asserted_no_binding_no_runtime",
                "scope": submitted["scope"], "observations": submitted["observations"],
                "receiver_binding": "unknown", "runtime_relation": "unknown"}
    # JSON bool/int equality in Python is weaker than wire equality. Compare
    # canonical serialized types as well as the complete closed field graph.
    canonical = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    if canonical(value) != canonical(expected):
        raise failure("RECEIPT_INVALID")
    return value
