"""Owned exact-byte examples; browser tests use real comparison HTTP paths."""
import hashlib
import zipfile


def build_line_diff_archives(root):
    markup = '<img src=x onerror=globalThis.ownedLineDiffInjected=true>'
    files = {
        'AUnicode.bsl': ('\ufeff// Кириллица 😀 ' + markup + '\r\nстарое\rхвост',
                         '// Кириллица 😀 ' + markup + '\r\nновое\nхвост'),
        'BNewline.os': ('одинаково\r\n', 'одинаково\n'),
        'CBom.bsp': ('\ufeffодинаково\n', 'одинаково\n'),
        'DEmptyAdded.bsl': (None, ''),
        'EEmptyDeleted.bsl': ('', None),
        'FAdded.os': (None, 'добавлено😀\n'),
        'GDeleted.os': ('удалено😀\n', None),
        'HPaged.bsl': (''.join(f'строка {i:03d}\n' for i in range(401)),
                       ''.join(f'строка {i:03d}\n' for i in range(401)) + 'конец'),
        'IWorkLimit.bsl': ('a\nb\n' * 550, 'b\na\n' * 550),
        'JInvalid.bsl': (b'\xff', b'\xfe'),
        'LDoubleBom.bsl': ('\ufeff\ufeffстарое\n', '\ufeff\ufeffновое\n'),
        'MInteriorBom.bsl': ('начало\n\ufeffстарое\n', 'начало\n\ufeffновое\n'),
        'KLongLine.os': ('x' * 18000 + '\n', 'y' * 18000 + '\n'),
    }
    data = {'files': {}, 'archives': {}}
    for name, sides in files.items():
        data['files'][name] = {}
        for side, value in zip(('before', 'after'), sides):
            raw = value.encode('utf-8') if isinstance(value, str) else value
            data['files'][name][side] = {'text': value if isinstance(value, str) else None,
                'present': raw is not None, 'sha256': hashlib.sha256(raw).hexdigest() if raw is not None else None,
                'size_bytes': len(raw) if raw is not None else None}
    for side_index, side in enumerate(('before', 'after')):
        archive = root / f'line-diff-{side}.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr('Catalogs/LineDiff.xml', '<MetaDataObject><Catalog><Properties><Name>LineDiff</Name></Properties></Catalog></MetaDataObject>')
            for name, values in files.items():
                if values[side_index] is not None:
                    output.writestr(name, values[side_index])
        data['archives'][side] = {'path': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    return data
