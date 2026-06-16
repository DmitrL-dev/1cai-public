import asyncio
import os
import logging
import sys

# Добавляем корень проекта в sys.path
sys.path.append(os.getcwd())

from src.ai.self_healing_code import SelfHealingCode

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DemoHealer")

async def run_demo():
    print("\n🔥 [DEMO] Starting Local Self-Healing Demo\n")
    
    # 1. Создаем сломанный файл
    target_file = "broken_script_demo.py"
    broken_code = """
def calculate_sum(a, b):
    if a > b  # MISSING COLON HERE!
        return a + b
    else:
        return b
"""
    with open(target_file, "w") as f:
        f.write(broken_code)
    
    print(f"❌ Created broken file: {target_file}")
    print("-" * 40)
    print(broken_code.strip())
    print("-" * 40)
    
    # 2. Инициализируем целителя (без реального LLM)
    # Мы используем Mock провайдер, но сам SelfHealingCode теперь имеет эвристики
    healer = SelfHealingCode(llm_provider=None) 
    
    try:
        # 3. Пытаемся выполнить код, чтобы поймать ошибку
        print("\n💥 Executing broken code to trigger error...")
        try:
            compile(broken_code, target_file, 'exec')
        except SyntaxError as e:
            print(f"   Caught SyntaxError: {e}")
            
            # 4. Запускаем лечение
            print("\n🚑 Summoning Self-Healing Agent...")
            
            # Формируем контекст ошибки вручную (как это делал бы мониторинг)
            context = {
                "file_path": target_file,
                "line_number": e.lineno,
                "code_snippet": broken_code.split('\n')[e.lineno - 1] if e.lineno else ""
            }
            
            fix = await healer.handle_error(e, context)
            
            if fix:
                print(f"\n✅ FIX APPLIED! ID: {fix.id}")
                print(f"   Description: {fix.description}")
                
                # 5. Проверяем результат
                with open(target_file, "r") as f:
                    fixed_content = f.read()
                
                print("\n✨ Fixed Content:")
                print("-" * 40)
                print(fixed_content.strip())
                print("-" * 40)
                
                # Проверка компиляции
                try:
                    compile(fixed_content, target_file, 'exec')
                    print("\n🎉 Verification: Fixed code compiles successfully!")
                except Exception as verify_err:
                    print(f"\n❌ Verification failed: {verify_err}")
            else:
                print("\n❌ Agent failed to generate a fix.")
                
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Cleanup
        if os.path.exists(target_file):
            os.remove(target_file)
            print(f"\n🧹 Cleaned up {target_file}")

if __name__ == "__main__":
    asyncio.run(run_demo())

