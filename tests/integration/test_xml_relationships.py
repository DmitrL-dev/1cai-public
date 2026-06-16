import os
import tempfile
import pytest
from src.ai.code_analysis.graph_builder import OneCCodeGraphBuilder
from src.ai.code_analysis.graph import InMemoryCodeGraphBackend, NodeKind, EdgeKind

SAMPLE_CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.1">
	<Catalog uuid="12345-67890-abcde">
		<Properties>
			<Name>Goods</Name>
		</Properties>
	</Catalog>
</MetaDataObject>
"""

SAMPLE_SUBSYSTEM = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.1">
	<Subsystem uuid="aaaaa-bbbbb-ccccc">
		<Properties>
			<Name>Sales</Name>
			<Content>
				<Item>Catalog.Goods</Item>
			</Content>
		</Properties>
	</Subsystem>
</MetaDataObject>
"""

@pytest.mark.asyncio
async def test_xml_relationships():
    backend = InMemoryCodeGraphBackend()
    builder = OneCCodeGraphBuilder(backend)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Catalog file
        with open(os.path.join(tmpdir, "Catalog_Goods.xml"), "w", encoding="utf-8") as f:
            f.write(SAMPLE_CATALOG)
            
        # Create Subsystem file
        with open(os.path.join(tmpdir, "Subsystem_Sales.xml"), "w", encoding="utf-8") as f:
            f.write(SAMPLE_SUBSYSTEM)
            
        # Build graph
        stats = await builder.build_from_xml(tmpdir, recursive=True)
        
        assert stats["nodes_created"] == 2
        assert stats["edges_created"] == 1
        
        # Verify nodes
        subsystem_node = await backend.find_nodes(kind=NodeKind.BSL_SUBSYSTEM)
        assert len(subsystem_node) == 1
        assert subsystem_node[0].display_name == "Sales"
        
        catalog_node = await backend.find_nodes(kind=NodeKind.BSL_CATALOG)
        assert len(catalog_node) == 1
        assert catalog_node[0].display_name == "Goods"
        
        # Verify edge
        neighbors = await backend.neighbors(subsystem_node[0].id, kinds=[EdgeKind.OWNS])
        assert len(neighbors) == 1
        assert neighbors[0].id == catalog_node[0].id
