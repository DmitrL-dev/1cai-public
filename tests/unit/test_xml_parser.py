import os
import tempfile
from src.ai.code_analysis.parsers.xml_parser import OneCXMLParser
from src.ai.code_analysis.graph import NodeKind

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.1">
	<Catalog uuid="12345-67890-abcde">
		<InternalInfo>
			<xr:GeneratedType name="CatalogObject.Товары" category="Object">
				<xr:TypeId>11111-22222</xr:TypeId>
				<xr:ValueId>33333-44444</xr:ValueId>
			</xr:GeneratedType>
		</InternalInfo>
		<Properties>
			<Name>Товары</Name>
			<Synonym>
				<v8:item>
					<v8:lang>ru</v8:lang>
					<v8:content>Товары и услуги</v8:content>
				</v8:item>
			</Synonym>
			<Comment>Основной справочник номенклатуры</Comment>
		</Properties>
		<ChildObjects>
			<Attribute uuid="aaaaa-bbbbb">
				<Properties>
					<Name>Артикул</Name>
					<Synonym>
						<v8:item>
							<v8:lang>ru</v8:lang>
							<v8:content>Артикул товара</v8:content>
						</v8:item>
					</Synonym>
					<Type>
						<v8:Type>xs:string</v8:Type>
						<v8:StringQualifiers>
							<v8:Length>25</v8:Length>
							<v8:AllowedLength>Variable</v8:AllowedLength>
						</v8:StringQualifiers>
					</Type>
				</Properties>
			</Attribute>
		</ChildObjects>
	</Catalog>
</MetaDataObject>
"""

class TestOneCXMLParser:
    def test_parse_catalog(self):
        parser = OneCXMLParser()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp:
            tmp.write(SAMPLE_XML)
            tmp_path = tmp.name
            
        try:
            nodes = parser.parse_file(tmp_path)
            assert len(nodes) == 1
            node = nodes[0]
            
            assert node.kind == NodeKind.BSL_CATALOG
            assert node.display_name == "Товары"
            assert node.props["Synonym_ru"] == "Товары и услуги"
            assert node.props["Comment"] == "Основной справочник номенклатуры"
            assert node.props["Uuid"] == "12345-67890-abcde"
            
            # Check attributes
            attributes = node.props["attributes"]
            assert len(attributes) == 1
            attr = attributes[0]
            assert attr["Name"] == "Артикул"
            assert attr["Synonym_ru"] == "Артикул товара"
            
        finally:
            os.remove(tmp_path)

    def test_unknown_object(self):
        parser = OneCXMLParser()
        xml = "<MetaDataObject><UnknownThing><Properties><Name>Test</Name></Properties></UnknownThing></MetaDataObject>"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp:
            tmp.write(xml)
            tmp_path = tmp.name
            
        try:
            nodes = parser.parse_file(tmp_path)
            assert len(nodes) == 1
            assert nodes[0].kind == NodeKind.BSL_METADATA_OBJECT
            assert nodes[0].display_name == "Test"
        finally:
            os.remove(tmp_path)
