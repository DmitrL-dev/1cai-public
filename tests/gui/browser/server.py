"""Owned synthetic project; real production HTTP/Rust paths, no test API endpoints."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rentgen_core import gui
from rentgen_core.local_identity import initialize_local_identity
from rentgen_core.registry import ProjectRegistry
from attribute_fixture import build_attribute_archive
from occurrence_fixture import build_occurrence_archive


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}


def main():
    built_binary = Path(os.environ['RENTGEN_INPUT_CORE_TEST_BINARY']).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='rentgen-browser-') as directory:
        root = Path(directory)
        # Cargo outputs may be hard-linked; production requires a single-link owned image.
        binary = root / 'rentgen-input-core'
        shutil.copyfile(built_binary, binary)
        binary.chmod(0o700)
        assert sha(binary) == sha(built_binary)
        identity = root / 'private' / 'identity.json'
        principal = initialize_local_identity(identity)
        source = root / 'source'
        source.mkdir()
        (source / 'untouched.txt').write_text('Owned synthetic browser acceptance only')
        registry = ProjectRegistry.create(root / 'registry.sqlite3')
        project = registry.register(principal, source_root=source, state_root=root / 'state', display_name='Synthetic browser acceptance')
        module = 'Процедура Тест()\n    Сообщить("Synthetic only");\nКонецПроцедуры\n'
        xml = ('<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
               '<Catalog uuid="11111111-1111-4111-8111-111111111111">'
               '<Properties><Name>Products</Name><Code>ARTICLE</Code></Properties>'
               '<ChildObjects/></Catalog></MetaDataObject>')
        archives = {}
        for label in ('first', 'second'):
            archive = root / f'{label}.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
                output.writestr('Catalogs/Products.xml', xml)
                output.writestr('Catalogs/Products/Ext/ObjectModule.bsl', module)
                output.writestr('owned-marker.txt', label)
            archives[label] = {'path': str(archive), 'sha256': sha(archive)}
        many_name = 'ПоследнийОбъект201'
        many_synonym = 'УникальныйСиноним201'
        many_stem = 'Object200' + 'LongOwnedPath' * 12
        many_path = f'Catalogs/{many_stem}.xml'
        many_xml = None
        archive = root / 'many.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            for index in range(201):
                name = many_name if index == 200 else f'Object{index:03d}'
                properties = f'<Name>{name}</Name>'
                if index == 200:
                    properties += f'<Synonym><item><lang>ru</lang><content>{many_synonym}</content></item></Synonym>'
                content = ('<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
                           '<Catalog uuid="11111111-1111-4111-8111-111111111111">'
                           f'<Properties>{properties}</Properties><ChildObjects/>'
                           '</Catalog></MetaDataObject>')
                stem = many_stem if index == 200 else f'Object{index:03d}'
                output.writestr(f'Catalogs/{stem}.xml', content)
                if index == 200:
                    many_xml = content
                output.writestr(f'Catalogs/{stem}/Ext/ObjectModule.bsl', module)
            output.writestr(f'Catalogs/{many_stem}/Ext/ПозднийМодуль.os', module)
            output.writestr(f'Catalogs/{many_stem}/Ext/ДругойМодуль.bsp', module)
            output.writestr(f'Catalogs/{many_stem}Neighbor/Ext/Neighbor.bsl', module)
        archives['many'] = {'path': str(archive), 'sha256': sha(archive)}
        archive = root / 'paged.zip'
        page_xml = None
        page_module = None
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            for index in range(401):
                content = ('<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
                           '<Catalog uuid="11111111-1111-4111-8111-111111111111">'
                           f'<Properties><Name>ОбъектСтраницы{index:03d}</Name></Properties>'
                           '<ChildObjects/></Catalog></MetaDataObject>')
                output.writestr(f'Catalogs/Page{index:03d}.xml', content)
                code = f'// Owned pagination {index:03d}\n' + module
                output.writestr(f'Catalogs/Page400/Ext/Модуль{index:03d}.bsl', code)
                if index == 400:
                    page_xml, page_module = content, code
        archives['paged'] = {'path': str(archive), 'sha256': sha(archive)}
        source_query = 'Фрагмент😀'
        source_html = '<img src=x onerror=globalThis.ownedSourceInjected=true>'
        source_module = None
        archive = root / 'source-text.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr('Catalogs/SourceOwner.xml', xml.replace('Products', 'SourceOwner'))
            for index in range(201):
                code = f'// first\r\n// {source_query} {index:03d} {source_html}\r// {source_query} repeated\n'
                if index == 0:
                    code = '\ufeff' + code
                output.writestr(f'Catalogs/SourceOwner/Ext/Code{index:03d}.bsl', code)
                if index == 200:
                    source_module = code
            output.writestr('Catalogs/SourceOwner/Ext/Zlarge.bsl', b'x' * (256 * 1024 + 1))
            output.writestr('Catalogs/SourceOwner/Ext/Zinvalid.os', b'\xff')
            output.writestr('Catalogs/SourceOwner/Ext/Zcontrol.bsp', b'bad\x00')
        archives['source'] = {'path': str(archive), 'sha256': sha(archive)}
        attributes = build_attribute_archive(root)
        archives['attributes'] = attributes.pop('archive')
        occurrences = build_occurrence_archive(root)
        archives['occurrences'] = occurrences.pop('archive')
        corrupt = root / 'corrupt.zip'
        corrupt.write_bytes(b'Owned deliberately invalid ZIP')
        compare_code = {}
        for side in ('before', 'after'):
            archive = root / f'compare-{side}.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
                output.writestr('Catalogs/Products.xml', xml)
                for index in range(401):
                    text = f'// {side} {index} Кириллица 😀 <img src=x onerror=alert(1)>\nПроцедура Тест()\nКонецПроцедуры\n'
                    output.writestr(f'CommonModules/Compare{index:03d}.bsl', text)
                    if index == 400:
                        compare_code[side] = text
                output.writestr(f'Only-{side}.os', side)
                output.writestr('Binary.bin', b'\xff' + side.encode())
                output.writestr('Large.bsp', side.encode() * 60000)
            archives[f'compare_{side}'] = {'path': str(archive), 'sha256': sha(archive)}
        before = snapshot(root)
        app = gui.Workspace(gui.Config(registry.path, identity, project.project_id, binary, sha(binary)))
        server = gui.Server(app)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        thread.start()
        try:
            # Private pipe only: callers must never log this session bootstrap.
            print(json.dumps({'origin': server.origin, 'token': app.token, 'archives': archives,
                              'attributes': attributes,
                              'occurrences': occurrences,
                              'corrupt': str(corrupt), 'module': module, 'compare_code': compare_code,
                              'compare_hashes': {side: hashlib.sha256(code.encode()).hexdigest() for side, code in compare_code.items()},
                              'many_name': many_name, 'many_synonym': many_synonym, 'many_path': many_path,
                              'many_xml': many_xml, 'many_xml_sha256': hashlib.sha256(many_xml.encode()).hexdigest(),
                              'source_query': source_query, 'source_html': source_html, 'source_module': source_module,
                              'source_module_sha256': hashlib.sha256(source_module.encode()).hexdigest(),
                              'page_xml': page_xml, 'page_module': page_module,
                              'page_xml_sha256': hashlib.sha256(page_xml.encode()).hexdigest(),
                              'page_module_sha256': hashlib.sha256(page_module.encode()).hexdigest(),
                              'module_sha256': hashlib.sha256(module.encode()).hexdigest()}), flush=True)
            sys.stdin.readline()
        finally:
            app.begin_close()
            server.shutdown()
            server.server_close()
            app.close()
            thread.join(timeout=3)
        assert not thread.is_alive()
        assert not Path(app.temp.name).exists()
        assert snapshot(root) == before, 'Browser flow changed owned project or input bytes'


if __name__ == '__main__':
    main()
