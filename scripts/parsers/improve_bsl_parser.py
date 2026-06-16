
#!/usr/bin/env python3
"""
Улучшенный парсер BSL кода на основе анализа Language 1C (BSL)
Версия: 2.0.0
"""

import re
from typing import Any, Dict, List, Optional


class ImprovedBSLParser:
    """
    Улучшенный парсер BSL кода
    Основан на понимании синтаксиса из Language 1C (BSL) расширения
    
    ОПТИМИЗАЦИЯ: Предкомпилированные regex паттерны
    """
    
    # Зарезервированные слова BSL
    RESERVED_KEYWORDS = {
        'Функция', 'Процедура', 'КонецФункции', 'КонецПроцедуры',
        'Если', 'Тогда', 'Иначе', 'КонецЕсли',
        'Пока', 'Цикл', 'КонецЦикла', 'Продолжить', 'Прервать',
        'Для', 'По', 'Из', 'Каждого', 'До',
        'Попытка', 'Исключение', 'КонецПопытки',
        'Перем', 'Знач', 'Экспорт', 'Новый', 'ЭтотОбъект',
        'Возврат', 'Истина', 'Ложь', 'Неопределено', 'Null'
    }
    
    # API 1С объекты
    API_OBJECTS = {
        'Запрос', 'ТаблицаЗначений', 'Структура', 'Соответствие',
        'СписокЗначений', 'ДеревоЗначений', 'РезультатЗапроса',
        'Справочники', 'Документы', 'РегистрыСведений',
        'РегистрыНакопления', 'РегистрыБухгалтерии',
        'Константы', 'Перечисления'
    }
    
    def __init__(self):
        self.functions = []
        self.procedures = []
        self.regions = []
        self.api_usage = []
        
        # ОПТИМИЗАЦИЯ: Предкомпилируем regex паттерны
        # Вместо компиляции на каждой строке - один раз при инициализации
        self._func_pattern = re.compile(
            r'^\s*(?:Экспорт\s+)?(?:Функция|Процедура)\s+([\wА-Яа-я]+)\s*\(([^)]*)\)',
            re.IGNORECASE
        )
        self._region_pattern = re.compile(
            r'#Область\s+([^\n]+)',
            re.IGNORECASE
        )
        self._region_end_pattern = re.compile(
            r'#КонецОбласти',
            re.IGNORECASE
        )
        self._control_flow_pattern = re.compile(
            r'\b(?:Если|Пока|Для|Попытка)\b',
            re.IGNORECASE
        )
        self._control_end_pattern = re.compile(
            r'\b(?:КонецЕсли|КонецЦикла|Исключение)\b',
            re.IGNORECASE
        )
        self._function_end_pattern = re.compile(
            r'\s*Конец(?:Функции|Процедуры)\s*$',
            re.IGNORECASE
        )
        
        # API patterns
        self._api_patterns = {
            api_obj: re.compile(rf'\b{api_obj}\b', re.IGNORECASE)
            for api_obj in self.API_OBJECTS
        }
    
    def parse(self, code: str) -> Dict[str, Any]:
        """
        Парсинг BSL кода
        
        Args:
            code: Исходный BSL код
            
        Returns:
            Словарь с результатами парсинга
        """
        if not code or not code.strip():
            return {
                'functions': [],
                'procedures': [],
                'regions': [],
                'api_usage': [],
                'statistics': {}
            }
        
        # Очистка предыдущих результатов
        self.functions = []
        self.procedures = []
        self.regions = []
        self.api_usage = []
        
        # Извлечение областей
        self._extract_regions(code)
        
        # Извлечение функций и процедур
        self._extract_functions_and_procedures(code)
        
        # Извлечение использования API
        self._extract_api_usage(code)
        
        # Статистика
        statistics = {
            'total_functions': len(self.functions),
            'total_procedures': len(self.procedures),
            'total_regions': len(self.regions),
            'exported_functions': len([f for f in self.functions if f.get('exported', False)]),
            'exported_procedures': len([p for p in self.procedures if p.get('exported', False)]),
            'api_calls': len(self.api_usage)
        }
        
        return {
            'functions': self.functions,
            'procedures': self.procedures,
            'regions': self.regions,
            'api_usage': self.api_usage,
            'statistics': statistics
        }
    
    def _extract_regions(self, code: str):
        """Извлечение областей кода (#Область ... #КонецОбласти)"""
        # Паттерн для областей
        region_pattern = r'#Область\s+([^\n]+)\n(.*?)(?=#КонецОбласти|$)'
        
        for match in re.finditer(region_pattern, code, re.DOTALL | re.IGNORECASE | re.MULTILINE):
            region_name = match.group(1).strip()
            region_content = match.group(2).strip()
            
            # Находим конец области
            end_match = re.search(r'#КонецОбласти', code[match.end():], re.IGNORECASE)
            if end_match:
                end_pos = match.end() + end_match.end()
                region_full = code[match.start():end_pos]
            else:
                region_full = code[match.start():match.end()]
            
            self.regions.append({
                'name': region_name,
                'content': region_content,
                'full_content': region_full,
                'start_pos': match.start(),
                'end_pos': match.end()
            })
    
    def _extract_functions_and_procedures(self, code: str):
        """Извлечение функций и процедур из BSL кода"""
        lines = code.split('\n')
        current_func = None
        in_function = False
        function_lines = []
        brace_level = 0
        region_stack = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            original_line = line
            
            # Пропускаем пустые строки (но сохраняем в функции)
            if not stripped:
                if in_function:
                    function_lines.append(original_line)
                continue
            
            # Обработка областей
            if stripped.startswith('#Область'):
                region_match = self._region_pattern.search(stripped)
                if region_match:
                    region_stack.append(region_match.group(1).strip())
            
            elif stripped.startswith('#КонецОбласти'):
                if region_stack:
                    region_stack.pop()
            
            # Комментарии перед функцией
            comment_lines = []
            if i > 0:
                j = i - 1
                while j >= 0 and lines[j].strip() and (lines[j].strip().startswith('//') or lines[j].strip().startswith('/*')):
                    comment_lines.insert(0, lines[j].strip())
                    j -= 1
                if j >= 0 and not lines[j].strip():
                    # Пропускаем пустые строки
                    while j >= 0 and not lines[j].strip():
                        j -= 1
                    while j >= 0 and lines[j].strip() and (lines[j].strip().startswith('//') or lines[j].strip().startswith('/*')):
                        comment_lines.insert(0, lines[j].strip())
                        j -= 1
            
            # Проверка начала функции/процедуры
            # ОПТИМИЗАЦИЯ: Используем предкомпилированный паттерн
            func_match = self._func_pattern.search(stripped)
            
            if func_match:
                # Сохраняем предыдущую функцию если есть
                if current_func and function_lines:
                    current_func['code'] = '\n'.join(function_lines)
                    if current_func['type'] == 'Функция':
                        self.functions.append(current_func)
                    else:
                        self.procedures.append(current_func)
                
                # Начинаем новую функцию/процедуру
                func_type = 'Функция' if 'Функция' in stripped or 'функция' in stripped else 'Процедура'
                func_name = func_match.group(1)
                params_str = func_match.group(2)
                is_exported = 'Экспорт' in stripped or 'экспорт' in stripped
                
                # Детальное извлечение параметров
                params = self._extract_parameters_detailed(params_str)
                
                current_func = {
                    'name': func_name,
                    'type': func_type,
                    'code': '',
                    'params': params,
                    'params_count': len(params),
                    'exported': is_exported,
                    'region': region_stack[-1] if region_stack else None,
                    'comments': '\n'.join(comment_lines) if comment_lines else '',
                    'line_start': i + 1,
                    'line_end': None
                }
                function_lines = [original_line]
                in_function = True
                brace_level = 0
                continue
            
            # Если мы внутри функции
            if in_function and current_func:
                function_lines.append(original_line)
                
                # Подсчет уровней вложенности (ОПТИМИЗАЦИЯ: предкомпилированные паттерны)
                if self._control_flow_pattern.search(stripped):
                    brace_level += 1
                elif self._control_end_pattern.search(stripped):
                    brace_level = max(0, brace_level - 1)
                
                # Конец функции/процедуры
                if self._function_end_pattern.search(stripped) and brace_level == 0:
                    current_func['code'] = '\n'.join(function_lines)
                    current_func['line_end'] = i + 1
                    
                    if current_func['type'] == 'Функция':
                        self.functions.append(current_func)
                    else:
                        self.procedures.append(current_func)
                    
                    current_func = None
                    in_function = False
                    function_lines = []
                    brace_level = 0
        
        # Сохраняем последнюю функцию если файл обрывается
        if current_func and function_lines:
            current_func['code'] = '\n'.join(function_lines)
            if current_func['type'] == 'Функция':
                self.functions.append(current_func)
            else:
                self.procedures.append(current_func)
    
    def _extract_parameters_detailed(self, params_str: str) -> List[Dict[str, Any]]:
        """
        Детальное извлечение параметров с типами и значениями по умолчанию
        
        Форматы параметров:
        - Параметр
        - Параметр: Тип
        - Параметр = Значение
        - Параметр: Тип = Значение
        """
        if not params_str or not params_str.strip():
            return []
        
        params = []
        current_param = ""
        depth = 0
        
        for char in params_str:
            if char == '(':
                depth += 1
                current_param += char
            elif char == ')':
                depth -= 1
                current_param += char
            elif char == ',' and depth == 0:
                # Разделитель параметров
                param = self._parse_single_parameter(current_param.strip())
                if param:
                    params.append(param)
                current_param = ""
            else:
                current_param += char
        
        # Последний параметр
        if current_param.strip():
            param = self._parse_single_parameter(current_param.strip())
            if param:
                params.append(param)
        
        return params
    
    def _parse_single_parameter(self, param_str: str) -> Optional[Dict[str, Any]]:
        """Парсинг одного параметра"""
        if not param_str or not param_str.strip():
            return None
        
        param_str = param_str.strip()
        
        # Ищем тип параметра (формат: Имя: Тип)
        type_match = re.search(r'^([\wА-Яа-я]+)\s*:\s*([\wА-Яа-я]+)', param_str)
        if type_match:
            param_name = type_match.group(1)
            param_type = type_match.group(2)
            
            # Ищем значение по умолчанию (формат: Имя: Тип = Значение)
            default_match = re.search(r'=\s*(.+)$', param_str)
            default_value = default_match.group(1).strip() if default_match else None
            
            return {
                'name': param_name,
                'type': param_type,
                'default_value': default_value,
                'required': default_value is None
            }
        
        # Ищем значение по умолчанию без типа (формат: Имя = Значение)
        default_match = re.search(r'^([\wА-Яа-я]+)\s*=\s*(.+)$', param_str)
        if default_match:
            param_name = default_match.group(1)
            default_value = default_match.group(2).strip()
            
            return {
                'name': param_name,
                'type': None,
                'default_value': default_value,
                'required': False
            }
        
        # Просто имя параметра
        return {
            'name': param_str,
            'type': None,
            'default_value': None,
            'required': True
        }
    
    def _extract_api_usage(self, code: str):
        """Извлечение использования API 1С"""
        # ОПТИМИЗАЦИЯ: Используем предкомпилированные паттерны
        for api_obj, pattern in self._api_patterns.items():
            # Поиск использования API объекта
            for match in pattern.finditer(code):
                # Находим контекст использования (строка кода)
                lines = code[:match.start()].split('\n')
                line_num = len(lines)
                line_content = lines[-1] if lines else ""
                
                # Ищем строку с использованием
                code_lines = code.split('\n')
                if line_num <= len(code_lines):
                    full_line = code_lines[line_num - 1]
                    
                    self.api_usage.append({
                        'api_object': api_obj,
                        'line_number': line_num,
                        'line_content': full_line.strip(),
                        'usage_type': self._detect_usage_type(full_line)
                    })
    
    def _detect_usage_type(self, line: str) -> str:
        """Определение типа использования API"""
        line_lower = line.lower()
        
        if 'новый' in line_lower:
            return 'creation'
        elif 'найти' in line_lower or 'получить' in line_lower:
            return 'query'
        elif 'записать' in line_lower or 'удалить' in line_lower:
            return 'modification'
        else:
            return 'usage'


# Функции для обратной совместимости
def extract_bsl_functions(code: str) -> List[dict]:
    """Извлечение функций из BSL кода (улучшенная версия)"""
    parser = ImprovedBSLParser()
    result = parser.parse(code)
    
    # Преобразуем в старый формат для совместимости
    functions = []
    for func in result['functions']:
        functions.append({
            'name': func['name'],
            'code': func['code'],
            'params': [p['name'] for p in func['params']],
            'exported': func.get('exported', False),
            'region': func.get('region'),
            'comments': func.get('comments', ''),
            'line_start': func.get('line_start'),
            'line_end': func.get('line_end')
        })
    
    return functions


def extract_parameters(signature: str) -> List[str]:
    """Извлечение параметров из сигнатуры (улучшенная версия)"""
    parser = ImprovedBSLParser()
    params = parser._extract_parameters_detailed(signature)
    return [p['name'] for p in params]


if __name__ == "__main__":
    # Пример использования
    test_code = """
#Область ПрограммныйИнтерфейс

// Функция для получения значения
//
// Параметры:
//  Параметр - Строка - параметр функции
//
// Возвращаемое значение:
//  Строка - значение
//
Функция ПолучитьЗначение(Параметр) Экспорт
\tВозврат Параметр;
КонецФункции

// Процедура для выполнения действия
Процедура ВыполнитьДействие(Параметр1, Параметр2: Строка = "По умолчанию") Экспорт
\t// Код процедуры
\tЗапрос = Новый Запрос;
КонецПроцедуры

#КонецОбласти
    """
    
    parser = ImprovedBSLParser()
    result = parser.parse(test_code)
    
    print("Функции:")
    for func in result['functions']:
        print(f"  - {func['name']}: {len(func['params'])} параметров")
        print(f"    Экспорт: {func['exported']}")
        print(f"    Область: {func.get('region')}")
        print(f"    Параметры: {[p['name'] for p in func['params']]}")
    
    print("\nПроцедуры:")
    for proc in result['procedures']:
        print(f"  - {proc['name']}: {len(proc['params'])} параметров")
        print(f"    Экспорт: {proc['exported']}")
        print(f"    Параметры: {[p['name'] for p in proc['params']]}")
    
    print("\nОбласти:")
    for region in result['regions']:
        print(f"  - {region['name']}")
    
    print("\nИспользование API:")
    for api in result['api_usage']:
        print(f"  - {api['api_object']} на строке {api['line_number']}")





