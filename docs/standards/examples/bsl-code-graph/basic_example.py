
"""
Пример использования BSL Code Graph для построения графа из BSL модуля

Этот пример демонстрирует:
1. Построение графа из BSL модуля
2. Извлечение зависимостей
3. Анализ влияния изменений
"""

from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder


def build_bsl_code_graph_example():
    """Пример построения BSL Code Graph"""
    
    # Создать builder
    builder = OneCCodeGraphBuilder()
    
    # Пример BSL кода (в реальности читается из файла)
    bsl_code = """
    // Обработка.МояОбработка
    
    Процедура ПриСозданииНаСервере()
        // Создание объекта
        НовыйОбъект = Справочники.Товары.СоздатьЭлемент();
        НовыйОбъект.Наименование = "Новый товар";
        НовыйОбъект.Записать();
        
        // Выполнение запроса
        Запрос = Новый Запрос;
        Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары";
        Результат = Запрос.Выполнить();
    КонецПроцедуры
    
    Функция ПолучитьТовар(ТоварКод)
        Запрос = Новый Запрос;
        Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары ГДЕ Код = &Код";
        Запрос.УстановитьПараметр("Код", ТоварКод);
        Результат = Запрос.Выполнить();
        Возврат Результат.Выгрузить()[0];
    КонецФункции
    """
    
    # Построить граф
    graph = builder.build_from_bsl_code(
        code=bsl_code,
        module_name="Обработка.МояОбработка"
    )
    
    # Получить узлы
    print("Узлы в графе:")
    for node in graph.nodes:
        print(f"  - {node.kind}: {node.display_name} (id: {node.id})")
    
    # Получить связи
    print("\nСвязи в графе:")
    for edge in graph.edges:
        source_node = next(n for n in graph.nodes if n.id == edge.source)
        target_node = next(n for n in graph.nodes if n.id == edge.target)
        print(f"  - {source_node.display_name} --[{edge.kind}]--> {target_node.display_name}")
    
    # Анализ зависимостей
    print("\nЗависимости функции 'ПолучитьТовар':")
    dependencies = graph.get_dependencies("function_ПолучитьТовар")
    for dep in dependencies:
        print(f"  - {dep.display_name}")
    
    return graph


if __name__ == "__main__":
    graph = build_bsl_code_graph_example()
    print("\n✅ Граф построен успешно!")

