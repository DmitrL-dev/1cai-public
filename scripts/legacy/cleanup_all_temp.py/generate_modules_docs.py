
import json
import os

MODULES_DIR = "m1cai_modules"
DOCS_DIR = "docs/modules"
RENAMING_MAP_FILE = "m1cai_modules/module_renaming_mapping.json"
RENAMING_DICT_FILE = "m1cai_modules/renaming_dictionary.json"
ANALYSIS_FILE = "m1cai_modules/analysis_results.json"
README_FILE = "m1cai_modules/README.md"

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("Loading data...")
    renaming_map = load_json(RENAMING_MAP_FILE)
    renaming_dict = load_json(RENAMING_DICT_FILE)
    # analysis_results = load_json(ANALYSIS_FILE) # Might be too big or complex structure, let's rely on maps first

    # Get the recommended variant mapping (Variant 7a)
    variant = renaming_map["variants"]["variant_7a_m1sai"]["mapping"]
    
    # Reverse mapping (Old -> New) is already in 'variant'
    # We need New -> Old to find info
    new_to_old = {v: k for k, v in variant.items()}

    # Ensure docs dir exists
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)

    readme_links = []

    print("Generating documentation...")
    
    # Iterate over existing .bsl files in modules dir
    bsl_files = [f for f in os.listdir(MODULES_DIR) if f.endswith(".bsl")]
    
    for bsl_file in bsl_files:
        module_name_ru = os.path.splitext(bsl_file)[0]
        
        # Try to find original name
        old_name = new_to_old.get(module_name_ru)
        
        if not old_name:
            print(f"⚠️ Could not find mapping for {module_name_ru}")
            continue

        print(f"Processing {module_name_ru} (was {old_name})...")
        
        # Get description
        description = "Библиотека модулей 1С AI Stack."
        functions = []
        
        if old_name in renaming_dict.get("by_module", {}):
            module_info = renaming_dict["by_module"][old_name]
            description = module_info.get("description", description)
            functions = module_info.get("functions", [])

        # Generate MD content
        md_content = f"# {module_name_ru}\n\n"
        md_content += f"**Оригинальное название:** `{old_name}`\n\n"
        md_content += f"## Описание\n{description}\n\n"
        
        if functions:
            md_content += "## Функции\n\n| Английское (старое) | Русское (новое) | Приоритет |\n|---|---|---|\n"
            for func in functions:
                md_content += f"| `{func['english']}` | `{func['russian']}` | {func.get('priority', '')} |\n"
            md_content += "\n"
        else:
            md_content += "## Функции\n\n*Информация о функциях будет добавлена позже.*\n\n"

        md_content += "## Использование\n\n"
        md_content += "```bsl\n"
        md_content += f"// Пример вызова\nРезультат = {module_name_ru}.<Функция>(...);\n"
        md_content += "```\n\n"
        
        md_content += "---\n*Автоматически сгенерированная документация для проекта 1C AI Stack.*"

        # Write MD file
        doc_path = os.path.join(DOCS_DIR, f"{module_name_ru}.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        readme_links.append(f"| [{module_name_ru}](../docs/modules/{module_name_ru}.md) | {description} |")

        # Update BSL header
        bsl_path = os.path.join(MODULES_DIR, bsl_file)
        with open(bsl_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
            
        # Check if header needs update
        # Look for "// Модуль: ..." at the top
        needs_update = True
        if len(lines) > 0 and lines[0].startswith(f"// Модуль: {module_name_ru}"):
             # Check if description is filled
             if len(lines) > 2 and description in lines[2]:
                 needs_update = False
        
        if needs_update:
            # Create new header
            new_header = [
                f"// Модуль: {module_name_ru}\n",
                f"// Назначение: {description}\n",
                "//\n",
                "////////////////////////////////////////////////////////////////////////////////\n\n"
            ]
            
            # Find where to insert (replace existing header or prepend)
            # If file starts with comments, replace them if they look like a header
            start_idx = 0
            if len(lines) > 0 and lines[0].strip().startswith("//"):
                # Skip existing header lines
                while start_idx < len(lines) and lines[start_idx].strip().startswith("//") and "Область" not in lines[start_idx]:
                     start_idx += 1
            
            # Write back
            with open(bsl_path, "w", encoding="utf-8-sig") as f:
                f.writelines(new_header + lines[start_idx:])
            print(f"  Updated header in {bsl_file}")

    # Update README.md
    print("Updating README...")
    readme_content = "# Модули 1C AI Stack (M1cAI)\n\n"
    readme_content += "Список модулей библиотеки и ссылки на документацию.\n\n"
    readme_content += "| Модуль | Описание |\n|---|---|\n"
    readme_content += "\n".join(sorted(readme_links))
    readme_content += "\n\n## Установка\n\nПоместите файлы `.bsl` в папку модулей вашего проекта или подключите как расширение.\n"
    
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("Done.")

if __name__ == "__main__":
    main()

