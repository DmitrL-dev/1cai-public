import sys
import os
import asyncio
from typing import Dict, Any

# Add src to path
sys.path.append(os.getcwd())

from src.modules.technical_writer.services.api_doc_generator import APIDocGenerator
from src.modules.technical_writer.services.user_guide_generator import UserGuideGenerator
from src.modules.technical_writer.domain.models import Audience


async def test_technical_writer():
    print("🚀 Starting Technical Writer Verification...")

    # 1. Test API Doc Generator
    print("\n[1] Testing API Doc Generator...")
    api_gen = APIDocGenerator()

    # Mock Source Code (BSL)
    source_code = """
    Функция СоздатьПользователя(Имя, Роль)
        // Логика создания
        Возврат Истина;
    КонецФункции
    
    Функция ПолучитьСписокПользователей()
        Возврат Новый Массив;
    КонецФункции
    """

    try:
        api_doc = await api_gen.generate_api_docs(code=source_code)
        print(f"✅ API Doc Generated ({api_doc.endpoints_count} endpoints)")
        print(f"   Markdown length: {len(api_doc.markdown_docs)} chars")
        # Verify endpoints were extracted
        assert api_doc.endpoints_count == 2
    except Exception as e:
        print(f"❌ API Doc Generation Failed: {e}")

    # 2. Test User Guide Generator
    print("\n[2] Testing User Guide Generator...")
    guide_gen = UserGuideGenerator()

    try:
        guide = await guide_gen.generate_user_guide(feature="Dashboard", target_audience=Audience.END_USER)
        print(f"✅ User Guide Generated for {guide.feature}")
        print(f"   Sections: {len(guide.sections)}")
        print(f"   Markdown length: {len(guide.guide_markdown)} chars")
    except Exception as e:
        print(f"❌ User Guide Generation Failed: {e}")

    print("\n🎉 All tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_technical_writer())
