
"""
Процессор шаблонов для генерации кода 1С.

Выполняет замену переменных в шаблонах и формирует итоговый код.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TemplateVariable:
    """Переменная шаблона."""
    name: str
    description: str
    default_value: str = ""
    required: bool = True
    validation_pattern: str = ""
    example_value: str = ""
    
    def is_valid(self, value: str) -> bool:
        """Проверяет корректность значения переменной."""
        if not self.validation_pattern:
            return True
        
        return bool(re.match(self.validation_pattern, value))


@dataclass
class GeneratedCode:
    """Сгенерированный код."""
    object_name: str
    object_type: str
    code_modules: Dict[str, str]
    form_layout: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    variables_used: List[str] = field(default_factory=list)
    validation_results: List[str] = field(default_factory=list)
    generation_time: datetime = field(default_factory=datetime.utcnow)


class TemplateProcessor:
    """Процессор для генерации кода из шаблонов."""
    
    def __init__(self, template_library):
        """
        Инициализация процессора.
        
        Args:
            template_library: Экземпляр TemplateLibrary
        """
        self.template_library = template_library
        self.logger = logging.getLogger(__name__)
        
        # Встроенные переменные для всех шаблонов
        self.builtin_variables = {
            'current_date': datetime.now().strftime('%d.%m.%Y'),
            'current_time': datetime.now().strftime('%H:%M:%S'),
            'object_type': 'object_type',
            'user_name': 'Пользователь',
            'version': '1.0.0'
        }
        
        # Безопасные паттерны для замены
        self.safe_patterns = {
            'identifier': r'^[a-zA-Zа-яА-Я_][a-zA-Zа-яА-Я0-9_]*$',
            'string': r'^[^<>"\']*$',
            'number': r'^\d+$',
            'comment': r'^/\*.*\*/$'
        }
    
    def generate_from_template(self, 
                             template_name: str, 
                             variables: Dict[str, str],
                             object_name: str = None) -> GeneratedCode:
        """
        Генерирует код из шаблона.
        
        Args:
            template_name: Имя шаблона
            variables: Значения переменных
            object_name: Имя создаваемого объекта
            
        Returns:
            GeneratedCode: Сгенерированный код
        """
        # Загружаем шаблон
        template = self.template_library.get_template_by_name(template_name)
        if not template:
            raise ValueError(f"Шаблон '{template_name}' не найден")
        
        # Проверяем обязательные переменные
        self._validate_variables(template, variables)
        
        # Объединяем переменные с встроенными
        all_variables = {**self.builtin_variables, **variables}
        if object_name:
            all_variables['object_name'] = object_name
            all_variables['ObjectName'] = self._to_pascal_case(object_name)
            all_variables['objectName'] = self._to_camel_case(object_name)
        
        # Генерируем код для каждого модуля
        generated_modules = {}
        for module_name, module_code in template.template_content.items():
            generated_code = self._process_module_code(module_code, all_variables)
            generated_modules[module_name] = generated_code
        
        # Генерируем макет формы если есть
        form_layout = None
        if template.form_layout:
            form_layout = self._process_form_layout(template.form_layout, all_variables)
        
        # Создаем результат
        result = GeneratedCode(
            object_name=object_name or variables.get('object_name', 'НовыйОбъект'),
            object_type=template.metadata.object_type,
            code_modules=generated_modules,
            form_layout=form_layout,
            variables_used=list(variables.keys()),
            validation_results=self._validate_generated_code(generated_modules, template)
        )
        
        return result
    
    def _validate_variables(self, template: Any, variables: Dict[str, str]):
        """Проверяет корректность переменных."""
        missing_required = []
        invalid_values = []
        
        for var_name, var_info in template.variables.items():
            if var_info.get('required', True) and var_name not in variables:
                missing_required.append(var_name)
            
            if var_name in variables:
                validation_pattern = var_info.get('validation_pattern', '')
                if validation_pattern and not re.match(validation_pattern, variables[var_name]):
                    invalid_values.append(f"{var_name}: {variables[var_name]}")
        
        if missing_required:
            raise ValueError(f"Отсутствуют обязательные переменные: {', '.join(missing_required)}")
        
        if invalid_values:
            raise ValueError(f"Некорректные значения переменных: {', '.join(invalid_values)}")
    
    def _process_module_code(self, code: str, variables: Dict[str, str]) -> str:
        """Обрабатывает код модуля."""
        processed_code = code
        
        # Заменяем переменные
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            processed_code = processed_code.replace(placeholder, var_value)
        
        # Заменяем комментарии TODO
        processed_code = self._replace_todo_comments(processed_code, variables)
        
        # Применяем форматирование
        processed_code = self._apply_code_formatting(processed_code)
        
        return processed_code
    
    def _process_form_layout(self, layout: str, variables: Dict[str, str]) -> str:
        """Обрабатывает макет формы."""
        processed_layout = layout
        
        # Заменяем переменные в макете
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            processed_layout = processed_layout.replace(placeholder, var_value)
        
        return processed_layout
    
    def _replace_todo_comments(self, code: str, variables: Dict[str, str]) -> str:
        """Заменяет комментарии TODO на реальный код."""
        # Словарь замен для TODO комментариев
        todo_replacements = {
            r'// TODO: Добавить основную логику здесь': self._generate_main_logic(variables),
            r'// TODO: Добавить проверки': self._generate_validation_logic(variables),
            r'// TODO: Добавить обработку ошибок': self._generate_error_handling(variables),
            r'// TODO: Добавить текст запроса СКД': self._generate_skd_query(variables),
            r'// TODO: Добавить заполнение других реквизитов': self._generate_field_filling(variables),
            r'// TODO: Добавить дополнительные проверки': self._generate_additional_checks(variables),
            r'// TODO: Добавить движения по необходимым регистрам': self._generate_movements(variables),
            r'// TODO: Реализовать запись в систему аудита': self._generate_audit_code(),
        }
        
        processed_code = code
        for todo_pattern, replacement in todo_replacements.items():
            processed_code = re.sub(todo_pattern, replacement, processed_code, flags=re.MULTILINE)
        
        return processed_code
    
    def _generate_main_logic(self, variables: Dict[str, str]) -> str:
        """Генерирует основную логику."""
        object_type = variables.get('object_type', 'processing')
        
        if object_type == 'processing':
            return """
    // Основная логика обработки данных
    Сообщить("Начинается обработка данных...");
    
    // Получение параметров обработки
    ПараметрыОбработки = Новый Структура;
    ПараметрыОбработки.Вставить("ДатаНачала", ДатаНачала);
    ПараметрыОбработки.Вставить("ДатаОкончания", ДатаОкончания);
    ПараметрыОбработки.Вставить("Организация", Организация);
    
    // Выполнение основной обработки
    ВыполнитьОбработкуДанных(ПараметрыОбработки);"""
        
        elif object_type == 'report':
            return """
    // Построение отчета
    Сообщить("Формирование отчета...");
    
    // Установка параметров отчета
    КомпоновщикНастроек.Настройки.Параметры.ДатаНачала.Значение = ДатаНачала;
    КомпоновщикНастроек.Настройки.Параметры.ДатаОкончания.Значение = ДатаОкончания;
    
    СформироватьОтчет();"""
        
        return "    // Основная логика"
    
    def _generate_validation_logic(self, variables: Dict[str, str]) -> str:
        """Генерирует логику валидации."""
        return """
    // Валидация входных данных
    Если ПустаяСтрока(Наименование) Тогда
        Сообщить("Наименование обязательно для заполнения!");
        Возврат Ложь;
    КонецЕсли;
    
    Если НЕ ЗначениеЗаполнено(Дата) Тогда
        Сообщить("Дата должна быть заполнена!");
        Возврат Ложь;
    КонецЕсли;
    
    Возврат Истина;"""
    
    def _generate_error_handling(self, variables: Dict[str, str]) -> str:
        """Генерирует обработку ошибок."""
        return """
    // Обработка ошибок
    Попытка
        ВыполнитьОперацию();
    Исключение
        Сообщить("Ошибка выполнения операции: " + ОписаниеОшибки());
        ЗаписатьЛогОшибки(ОписаниеОшибки());
        Возврат Ложь;
    КонецПопытки;
    
    Возврат Истина;"""
    
    def _generate_skd_query(self, variables: Dict[str, str]) -> str:
        """Генерирует запрос СКД."""
        return """
        |ВЫБРАТЬ
        |    Ссылка КАК Ссылка,
        |    Наименование КАК Наименование,
        |    Код КАК Код
        |ИЗ
        |    Справочник.Номенклатура КАК Номенклатура
        |ГДЕ
        |    Номенклатура.ПометкаУдаления = ЛОЖЬ
        |УПОРЯДОЧИТЬ ПО
        |    Наименование"""
    
    def _generate_field_filling(self, variables: Dict[str, str]) -> str:
        """Генерирует заполнение полей."""
        return """
        // Заполнение дополнительных реквизитов
        Если Элемент.Ключ = "ДатаСоздания" И НЕ ЗначениеЗаполнено(ДатаСоздания) Тогда
            ДатаСоздания = ТекущаяДата();
        КонецЕсли;
        
        Если Элемент.Ключ = "Автор" И НЕ ЗначениеЗаполнено(Автор) Тогда
            Автор = ПараметрыСеанса.ТекущийПользователь;
        КонецЕсли;"""
    
    def _generate_additional_checks(self, variables: Dict[str, str]) -> str:
        """Генерирует дополнительные проверки."""
        return """
        // Дополнительные проверки перед записью
        Если Дата > ТекущаяДата() Тогда
            Сообщить("Дата не может быть в будущем!");
            Отказ = Истина;
            Возврат;
        КонецЕсли;
        
        // Проверка уникальности наименования
        Если НЕ ЭтоНовый() Тогда
            Запрос = Новый Запрос;
            Запрос.Текст = "
                |ВЫБРАТЬ ПЕРВЫЕ 1
                |    Ссылка
                |ИЗ
                |    Справочник.Номенклатура
                |ГДЕ
                |    Наименование = &Наименование
                |    И Ссылка <> &Ссылка";
            Запрос.УстановитьПараметр("Наименование", Наименование);
            Запрос.УстановитьПараметр("Ссылка", Ссылка);
            
            Результат = Запрос.Выполнить();
            Если НЕ Результат.Пустой() Тогда
                Сообщить("Элемент с таким наименованием уже существует!");
                Отказ = Истина;
            КонецЕсли;
        КонецЕсли;"""
    
    def _generate_movements(self, variables: Dict[str, str]) -> str:
        """Генерирует движения по регистрам."""
        return """
    // Движения по регистру сведений
    Движения = Движения.МойРегистр;
    
    Для Каждого СтрокаТЧ Из ТабличнаяЧасть1 Цикл
        Движение = Движения.Добавить();
        Движение.Период = Дата;
        Движение.Регистратор = Ссылка;
        Движение.Номенклатура = СтрокаТЧ.Номенклатура;
        Движение.Количество = СтрокаТЧ.Количество;
        Движение.Сумма = СтрокаТЧ.Сумма;
    КонецЦикла;
    
    // Движения по регистру накопления
    Движения = Движения.МойРегистрНакопления;
    
    Для Каждого СтрокаТЧ Из ТабличнаяЧасть1 Цикл
        Движение = Движения.Добавить();
        Движение.ВидДвижения = ВидДвиженияНакопления.Приход;
        Движение.Период = Дата;
        Движение.Регистратор = Ссылка;
        Движение.Номенклатура = СтрокаТЧ.Номенклатура;
        Движение.Количество = СтрокаТЧ.Количество;
    КонецЦикла;"""
    
    def _generate_audit_code(self) -> str:
        """Генерирует код аудита."""
        return """
    // Запись в систему аудита
    Попытка
        Аудит = РегистрыСведений.АудитИзменений.СоздатьМенеджерЗаписи();
        Аудит.Период = ТекущаяДата();
        Аудит.Пользователь = ПараметрыСеанса.ТекущийПользователь;
        Аудит.Действие = "Создание документа";
        Аудит.Объект = Ссылка;
        Аудит.Описание = "Создан документ " + Ссылка;
        Аудит.Записать();
    Исключение
        // Игнорируем ошибки аудита, не прерываем основную операцию
    КонецПопытки;"""
    
    def _apply_code_formatting(self, code: str) -> str:
        """Применяет форматирование к коду."""
        # Убираем лишние переносы строк
        lines = code.split('\n')
        formatted_lines = []
        prev_empty = False
        
        for line in lines:
            # Убираем trailing spaces
            line = line.rstrip()
            
            # Убираем множественные пустые строки
            if line.strip() == '':
                if not prev_empty:
                    formatted_lines.append('')
                prev_empty = True
            else:
                formatted_lines.append(line)
                prev_empty = False
        
        return '\n'.join(formatted_lines)
    
    def _to_pascal_case(self, text: str) -> str:
        """Преобразует текст в PascalCase."""
        words = re.findall(r'[a-zA-Zа-яА-Я0-9]+', text)
        return ''.join(word.capitalize() for word in words)
    
    def _to_camel_case(self, text: str) -> str:
        """Преобразует текст в camelCase."""
        words = re.findall(r'[a-zA-Zа-яА-Я0-9]+', text)
        if not words:
            return text
        return words[0].lower() + ''.join(word.capitalize() for word in words[1:])
    
    def _validate_generated_code(self, code_modules: Dict[str, str], template: Any) -> List[str]:
        """Валидирует сгенерированный код."""
        validation_results = []
        
        for module_name, code in code_modules.items():
            # Проверка на наличие TODO комментариев
            if 'TODO' in code:
                validation_results.append(f"В модуле '{module_name}' остались комментарии TODO")
            
            # Проверка баланса скобок
            if not self._check_brackets_balance(code):
                validation_results.append(f"В модуле '{module_name}' нарушен баланс скобок")
            
            # Проверка корректности комментариев
            if not self._check_comments_balance(code):
                validation_results.append(f"В модуле '{module_name}' нарушен баланс комментариев")
        
        # Проверка соответствия шаблону
        for rule in template.validation_rules:
            if not self._check_validation_rule(rule, code_modules):
                validation_results.append(f"Нарушено правило валидации: {rule}")
        
        return validation_results
    
    def _check_brackets_balance(self, code: str) -> bool:
        """Проверяет баланс скобок в коде."""
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for char in code:
            if char in brackets:
                stack.append(char)
            elif char in brackets.values():
                if not stack or brackets[stack.pop()] != char:
                    return False
        
        return len(stack) == 0
    
    def _check_comments_balance(self, code: str) -> bool:
        """Проверяет баланс многострочных комментариев."""
        # Простой поиск незакрытых комментариев
        comment_start = code.find('/*')
        comment_end = code.find('*/')
        
        while comment_start != -1:
            if comment_end == -1 or comment_end < comment_start:
                return False
            comment_start = code.find('/*', comment_end + 2)
            comment_end = code.find('*/', comment_end + 2)
        
        return True
    
    def _check_validation_rule(self, rule: str, code_modules: Dict[str, str]) -> bool:
        """Проверяет конкретное правило валидации."""
        # Простая реализация проверки правил
        rule_lower = rule.lower()
        
        if 'проверить доступность данных' in rule_lower:
            return any('Доступность' in code or 'Права' in code for code in code_modules.values())
        
        if 'проверить права пользователя' in rule_lower:
            return any('ПараметрыСеанса' in code or 'Пользователь' in code for code in code_modules.values())
        
        if 'проверить корректность' in rule_lower:
            # Базовая проверка наличия валидации
            return any('ПустаяСтрока' in code or 'ЗначениеЗаполнено' in code for code in code_modules.values())
        
        # Для остальных правил считаем, что они выполнены
        return True
    
    def preview_template(self, template_name: str, variables: Dict[str, str]) -> Dict[str, str]:
        """Предпросмотр шаблона с заменой переменных."""
        template = self.template_library.get_template_by_name(template_name)
        if not template:
            raise ValueError(f"Шаблон '{template_name}' не найден")
        
        preview = {}
        for module_name, module_code in template.template_content.items():
            processed_code = self._process_module_code(module_code, variables)
            preview[module_name] = processed_code
        
        return preview
    
    def get_template_variables(self, template_name: str) -> List[TemplateVariable]:
        """Возвращает список переменных шаблона."""
        template = self.template_library.get_template_by_name(template_name)
        if not template:
            raise ValueError(f"Шаблон '{template_name}' не найден")
        
        variables = []
        for var_name, var_info in template.variables.items():
            variables.append(TemplateVariable(
                name=var_name,
                description=var_info.get('description', ''),
                default_value=var_info.get('default', ''),
                required=var_info.get('required', True),
                validation_pattern=var_info.get('validation_pattern', ''),
                example_value=var_info.get('example', '')
            ))
        
        return variables


# Расширение TemplateLibrary для совместимости
def get_template_by_name(self, name: str) -> Optional[Any]:
    """Возвращает шаблон по имени."""
    for template in self._templates_cache.values():
        if template.metadata.name == name:
            return template
    return None


# Добавляем метод к классу TemplateLibrary
TemplateLibrary.get_template_by_name = get_template_by_name