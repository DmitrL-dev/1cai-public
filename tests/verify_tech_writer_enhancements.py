import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.technical_writer.services.ast_doc_generator import ASTUserGuideGenerator
from src.modules.technical_writer.domain.models import Audience

def verify_tech_writer_enhancements():
    print("Verifying Technical Writer Enhancements...")
    
    generator = ASTUserGuideGenerator()
    
    # Test Code
    code = """
class DataProcessor:
    \"\"\"
    Processes data for analytics.
    \"\"\"
    
    def process(self, data: list) -> dict:
        \"\"\"
        Main processing function.
        Args:
            data: Input list
        Returns:
            Processed dict
        \"\"\"
        return {"count": len(data)}
        
def utility_func():
    \"\"\"Helper function.\"\"\"
    pass
    """
    
    print("\nGenerating User Guide from code...")
    guide = generator.generate(code, "Data Processor", Audience.DEVELOPER)
    
    print(f"Feature: {guide.feature}")
    print(f"Sections: {len(guide.sections)}")
    
    for section in guide.sections:
        print(f" - {section.title}")
        
    # Assertions
    titles = [s.title for s in guide.sections]
    assert "Class: DataProcessor" in titles
    assert "Utility Functions" in titles
    
    # Check content
    markdown = guide.guide_markdown
    assert "Processes data for analytics" in markdown
    assert "Main processing function" in markdown
    
    print("\nTechnical Writer Enhancements Verified!")

if __name__ == "__main__":
    verify_tech_writer_enhancements()
