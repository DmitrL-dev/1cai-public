import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.technical_writer.services.mermaid_generator import MermaidGenerator

def verify_mermaid():
    print("Verifying Mermaid Generator...")
    
    generator = MermaidGenerator()
    
    code = """
class Animal:
    def breathe(self):
        pass

class Dog(Animal):
    def bark(self, volume):
        pass
        
class Cat(Animal):
    def meow(self):
        pass
    """
    
    print("\nGenerating Class Diagram...")
    diagram = generator.generate_class_diagram(code)
    
    print("\nGenerated Diagram:")
    print(diagram)
    
    # Assertions
    assert "classDiagram" in diagram
    assert "Animal <|-- Dog" in diagram
    assert "Animal <|-- Cat" in diagram
    assert "class Dog {" in diagram
    assert "+bark(volume)" in diagram
    
    print("\nMermaid Generator Verified Successfully!")

if __name__ == "__main__":
    verify_mermaid()
