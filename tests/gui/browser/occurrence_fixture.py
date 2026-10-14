"""Owned literal-occurrence bytes; expectations do not come from API replies."""
import hashlib
import zipfile


def build_occurrence_archive(root):
    query = 'Иголка😀'
    html = '<img src=x onerror=globalThis.ownedOccurrenceInjected=true>'
    # 402 repeated code points have exactly 401 overlapping two-character hits.
    # BOM, astral characters and three newline forms distinguish byte offsets,
    # UTF-16 indexes and the documented Unicode-codepoint positions.
    text = ('Я😀' + 'а' * 402 + 'x' * 600 + '\r\n'
            + f'Я😀{query} {html}\r'
            + f'é😀{query}\n'
            + f'中😀{query}\n')
    raw = b'\xef\xbb\xbf' + text.encode('utf-8')
    path = 'Catalogs/OccurrenceOwner/Ext/AOccurrences.bsl'
    other_path = 'Catalogs/OccurrenceOwner/Ext/ZOther.os'
    other_text = '// Other owned module\nСообщить("other-only");\n'
    xml = ('<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
           '<Catalog uuid="11111111-1111-4111-8111-111111111111">'
           '<Properties><Name>OccurrenceOwner</Name></Properties>'
           '<ChildObjects/></Catalog></MetaDataObject>')
    archive = root / 'occurrences.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr('Catalogs/OccurrenceOwner.xml', xml)
        output.writestr(path, raw)
        output.writestr(other_path, other_text)
    return {
        'archive': {'path': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
        'path': path, 'text': text, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
        'size_bytes': len(raw), 'characters': len(text),
        'other_path': other_path, 'other_text': other_text,
        'other_sha256': hashlib.sha256(other_text.encode()).hexdigest(),
        'query': query, 'html': html, 'overlap_query': 'аа', 'overlap_total': 401,
        'positions': [
            {'line': 2, 'column': 3, 'offset': 1008},
            {'line': 3, 'column': 3, 'offset': 1019 + len(html)},
            {'line': 4, 'column': 3, 'offset': 1029 + len(html)},
        ],
    }
