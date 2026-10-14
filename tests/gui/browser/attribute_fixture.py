"""Owned Designer XML examples for genuine browser-to-input-core acceptance."""
import hashlib
from xml.sax.saxutils import escape
import zipfile


def _properties(name, synonym=None, translations=()):
    text = f'<Name>{escape(name)}</Name>'
    localized = ([('ru', synonym)] if synonym is not None else []) + list(translations)
    if localized:
        text += '<Synonym>' + ''.join(
            f'<item><lang>{escape(locale)}</lang><content>{escape(value)}</content></item>'
            for locale, value in localized) + '</Synonym>'
    return f'<Properties>{text}</Properties>'


def _field(kind, name, synonym=None, uuid=None, translations=()):
    identity = f' uuid="{uuid}"' if uuid is not None else ''
    return f'<{kind}{identity}>{_properties(name, synonym, translations)}</{kind}>'


def _owner(kind, name, children, extra_properties=''):
    properties = _properties(name)
    if extra_properties:
        properties = properties.replace('</Properties>', extra_properties + '</Properties>')
    return ('<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
            f'<{kind} uuid="11111111-1111-4111-8111-111111111111">'
            f'{properties}<ChildObjects>{children}</ChildObjects>'
            f'</{kind}></MetaDataObject>')


def build_attribute_archive(root):
    """Return the ZIP and independently hashed exact owner XML, never API replies."""
    name = 'КоНтРаГеНт'
    synonym = 'Основной партнёр'
    english_synonym = 'SupplierSKU'
    nested_synonym = 'Партнёр строки'
    section_name = 'Строки😀'
    html_name = '<img src=x onerror=globalThis.ownedAttributeInjected=true>'
    html_synonym = '<svg onload=globalThis.ownedAttributeInjected=true>'
    uuid = '22222222-2222-4222-8222-222222222222'
    direct = _field('Attribute', name, synonym, uuid, (('en', english_synonym),))
    nested = ('<TabularSection uuid="33333333-3333-4333-8333-333333333333">'
              f'{_properties(section_name)}<ChildObjects>'
              f'{_field("Attribute", name, nested_synonym, "invalid-owned-uuid")}'
              '</ChildObjects></TabularSection>')
    decoy = _field('Attribute', 'ВнеОбластиПроверки')
    # Descendants in unrelated containers and owner properties are not fields.
    form = f'<Form>{_properties("OwnedForm")}<ChildObjects>{decoy}</ChildObjects></Form>'
    owner_xml = _owner('Catalog', 'Поставщики', direct + nested
                       + _field('Attribute', html_name, html_synonym) + form,
                       f'<Unrelated>{decoy}</Unrelated>')
    register_xml = _owner('InformationRegister', 'Остатки',
                          _field('Dimension', 'ИзмерениеПартнёр', 'Связанный контрагент')
                          + _field('Resource', 'РесурсПартнёр', 'Контрагент сумма'))
    bounded_xml = _owner('Document', 'Лимит', ''.join(
        _field('Attribute', f'МассовыйРеквизит{index:02d}') for index in range(25)))
    path = 'Catalogs/Поставщики.xml'
    archive = root / 'attributes.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr(path, owner_xml)
        output.writestr('InformationRegisters/Остатки.xml', register_xml)
        output.writestr('Documents/Лимит.xml', bounded_xml)
    return {
        'archive': {'path': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
        'name': name, 'synonym': synonym, 'english_synonym': english_synonym,
        'nested_synonym': nested_synonym,
        'section_name': section_name, 'uuid': uuid,
        'html_name': html_name, 'html_synonym': html_synonym,
        'path': path, 'xml': owner_xml,
        'xml_sha256': hashlib.sha256(owner_xml.encode()).hexdigest(),
    }
