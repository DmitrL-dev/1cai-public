
"""
Библиотека готовых шаблонов для генерации кода 1С.

Содержит готовые к использованию шаблоны для различных типов объектов.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class TemplateMetadata:
    """Метаданные шаблона."""
    name: str
    description: str
    version: str
    object_type: str  # processing, report, catalog, document
    complexity_level: str  # simple, standard, advanced, enterprise
    author: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    rating: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)


@dataclass
class CodeTemplate:
    """Шаблон кода для генерации."""
    metadata: TemplateMetadata
    template_content: Dict[str, str]  # Структура: {module_name: content}
    form_layout: Optional[str] = None  # Макет формы
    configuration: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    validation_rules: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует шаблон в словарь."""
        result = asdict(self)
        # Преобразуем datetime в строку для JSON
        result['metadata']['created_at'] = self.metadata.created_at.isoformat()
        result['metadata']['updated_at'] = self.metadata.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeTemplate':
        """Создает шаблон из словаря."""
        # Восстанавливаем datetime
        metadata_data = data['metadata']
        metadata_data['created_at'] = datetime.fromisoformat(metadata_data['created_at'])
        metadata_data['updated_at'] = datetime.fromisoformat(metadata_data['updated_at'])
        metadata = TemplateMetadata(**metadata_data)
        
        return cls(
            metadata=metadata,
            template_content=data['template_content'],
            form_layout=data.get('form_layout'),
            configuration=data.get('configuration', {}),
            variables=data.get('variables', {}),
            validation_rules=data.get('validation_rules', []),
            examples=data.get('examples', [])
        )


class TemplateLibrary:
    """Библиотека шаблонов для генерации кода 1С."""
    
    def __init__(self, templates_dir: Union[str, Path] = None):
        """
        Инициализация библиотеки шаблонов.
        
        Args:
            templates_dir: Директория с шаблонами
        """
        self.templates_dir = Path(templates_dir) if templates_dir else Path(__file__).parent
        self.logger = logging.getLogger(__name__)
        
        # Создаем подпапки для разных типов объектов
        self.object_types = ['processing', 'report', 'catalog', 'document']
        self._ensure_directories()
        
        # Загружаем все шаблоны
        self._templates_cache: Dict[str, CodeTemplate] = {}
        self._load_all_templates()
    
    def _ensure_directories(self):
        """Создает необходимые директории."""
        for obj_type in self.object_types:
            dir_path = self.templates_dir / obj_type
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _load_all_templates(self):
        """Загружает все шаблоны из файлов."""
        for obj_type in self.object_types:
            type_dir = self.templates_dir / obj_type
            
            for template_file in type_dir.glob("*.json"):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    
                    template = CodeTemplate.from_dict(template_data)
                    template_key = f"{obj_type}.{template.metadata.name}"
                    self._templates_cache[template_key] = template
                    
                    self.logger.info(f"Загружен шаблон: {template_key}")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка загрузки шаблона {template_file}: {e}")
    
    def get_template(self, object_type: str, template_name: str) -> Optional[CodeTemplate]:
        """Возвращает шаблон по типу объекта и имени."""
        template_key = f"{object_type}.{template_name}"
        return self._templates_cache.get(template_key)
    
    def list_templates(self, object_type: str = None) -> List[str]:
        """Возвращает список доступных шаблонов."""
        if object_type:
            return [key for key in self._templates_cache.keys() if key.startswith(f"{object_type}.")]
        
        return list(self._templates_cache.keys())
    
    def get_templates_by_complexity(self, complexity_level: str) -> List[CodeTemplate]:
        """Возвращает шаблоны по уровню сложности."""
        return [template for template in self._templates_cache.values() 
                if template.metadata.complexity_level == complexity_level]
    
    def search_templates(self, query: str) -> List[CodeTemplate]:
        """Поиск шаблонов по названию, описанию или тегам."""
        query_lower = query.lower()
        results = []
        
        for template in self._templates_cache.values():
            metadata = template.metadata
            if (query_lower in metadata.name.lower() or 
                query_lower in metadata.description.lower() or
                any(query_lower in tag.lower() for tag in metadata.tags)):
                results.append(template)
        
        return results
    
    def save_template(self, template: CodeTemplate) -> bool:
        """Сохраняет шаблон в файл."""
        try:
            obj_type = template.metadata.object_type
            template_file = self.templates_dir / obj_type / f"{template.metadata.name}.json"
            
            # Обновляем метаданные
            template.metadata.updated_at = datetime.utcnow()
            template.metadata.usage_count += 1
            
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
            
            # Обновляем кэш
            template_key = f"{obj_type}.{template.metadata.name}"
            self._templates_cache[template_key] = template
            
            self.logger.info(f"Шаблон сохранен: {template_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения шаблона: {e}")
            return False
    
    def create_processing_template(self) -> CodeTemplate:
        """Создает базовый шаблон обработки."""
        metadata = TemplateMetadata(
            name="basic_processing",
            description="Базовый шаблон обработки с простым функционалом",
            version="1.0.0",
            object_type="processing",
            complexity_level="simple",
            author="TemplateLibrary",
            tags=["basic", "simple", "template"]
        )
        
        template_content = {
            "module_object": """
&НаСервере
Процедура ВыполнитьОбработку() Экспорт
    // Основная логика обработки
    Сообщить("Выполняется обработка...");
    
    // TODO: Добавить основную логику здесь
    
    Возврат Истина;
КонецПроцедуры

&НаСервере
Функция ПолучитьРезультат() Экспорт
    // Возвращает результат обработки
    Возврат "Результат обработки";
КонецФункции
            """,
            "module_form": """
&НаКлиенте
Процедура КнопкаВыполнитьНажатие(Кнопка)
    // Обработчик кнопки "Выполнить"
    
    Состояние("Выполняется обработка...", 0);
    
    Результат = ВыполнитьОбработку();
    
    Если Результат Тогда
        Сообщить("Обработка завершена успешно");
        ОбновитьОтображениеДанных();
    Иначе
        Сообщить("Произошла ошибка при обработке");
    КонецЕсли;
    
    Состояние();
КонецПроцедуры

&НаКлиенте
Процедура КнопкаОтменаНажатие(Кнопка)
    // Обработчик кнопки "Отмена"
    Закрыть();
КонецПроцедуры
            """
        }
        
        form_layout = """
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:core="http://v8.1c.ru/8.1/core/core.xml">
    <FormItems>
        <FormGroup Item="Group1" UseAutoDeletion="false">
            <Items>
                <FormItem Item="КнопкаВыполнить" Type="Button" UseAutoDeletion="false">
                    <Properties>
                        <Title>Выполнить</Title>
                        <Picture>Icons.icon_play</Picture>
                    </Properties>
                    <Events>
                        <OnClick>КнопкаВыполнитьНажатие</OnClick>
                    </Events>
                </FormItem>
                <FormItem Item="КнопкаОтмена" Type="Button" UseAutoDeletion="false">
                    <Properties>
                        <Title>Отмена</Title>
                        <Picture>Icons.icon_cancel</Picture>
                    </Properties>
                    <Events>
                        <OnClick>КнопкаОтменаНажатие</OnClick>
                    </Events>
                </FormItem>
            </Items>
        </FormGroup>
    </FormItems>
</Form>
        """
        
        return CodeTemplate(
            metadata=metadata,
            template_content=template_content,
            form_layout=form_layout,
            validation_rules=[
                "Проверить доступность данных",
                "Проверить права пользователя",
                "Проверить корректность параметров"
            ],
            examples=[
                "Создание обработки для массового изменения цен",
                "Обработка импорта данных из файла",
                "Группировка и анализ данных"
            ]
        )
    
    def create_report_template(self) -> CodeTemplate:
        """Создает базовый шаблон отчета."""
        metadata = TemplateMetadata(
            name="basic_report",
            description="Базовый шаблон отчета с использованием СКД",
            version="1.0.0",
            object_type="report",
            complexity_level="standard",
            author="TemplateLibrary",
            tags=["basic", "report", "skd"],
            dependencies=["Система компоновки данных"],
            requirements=["Право на чтение данных"]
        )
        
        template_content = {
            "module_object": """
&НаСервере
Процедура СформироватьОтчет() Экспорт
    // Создание и настройка схемы компоновки данных
    СхемаКомпоновкиДанных = Новый СхемаКомпоновкиДанных;
    
    // Источник данных
    ИсточникДанных = СхемаКомпоновкиДанных.ИсточникиДанных.Добавить();
    ИсточникДанных.Имя = "ИсточникДанных";
    ИсточникДанных.СтрокаИсточникаДанных = "";
    
    // Набор данных
    НаборДанных = СхемаКомпоновкиДанных.НаборыДанных.Добавить(Тип("НаборДанныхЗапросСхемыКомпоновкиДанных"));
    НаборДанных.Имя = "ОсновнойНабор";
    НаборДанных.ИсточникДанных = "ИсточникДанных";
    
    // TODO: Добавить текст запроса СКД
    НаборДанных.Запрос = "
        |ВЫБРАТЬ
        |    *
        |ИЗ
        |    Справочник.Номенклатура";
    
    // Поля набора данных
    ПолеНабора = НаборДанных.Поля.Добавить(Тип("ПолеНабораДанныхСхемыКомпоновкиДанных"));
    ПолеНабора.Имя = "Ссылка";
    ПолеНабора.Заголовок = "Ссылка";
    
    ПолеНабора = НаборДанных.Поля.Добавить(Тип("ПолеНабораДанныхСхемыКомпоновкиДанных"));
    ПолеНабора.Имя = "Наименование";
    ПолеНабора.Заголовок = "Наименование";
    
    // Настройки компоновщика
    КомпоновщикНастроек.Инициализировать(Новый ИсточникДоступныхНастроекКомпоновкиДанных(СхемаКомпоновкиДанных));
    
    // Настройки по умолчанию
    Настройки = КомпоновщикНастроек.ПолучитьНастройки();
    КомпоновщикНастроек.ЗагрузитьНастройки(Настройки);
КонецПроцедуры

&НаСервере
Функция ПолучитьМакет() Экспорт
    Возврат ПолучитьМакет("Основной");
КонецФункции
            """,
            "module_form": """
&НаКлиенте
Процедура СформироватьНажатие(Кнопка)
    // Формирование отчета
    Состояние("Формирование отчета...", 0);
    
    // Вызов серверной процедуры
    Результат = ВыполнитьСервернуюПроцедуру();
    
    Если НЕ Результат.Выполнено Тогда
        Сообщить("Ошибка формирования отчета: " + Результат.СообщениеОбОшибке);
    КонецЕсли;
    
    Состояние();
КонецПроцедуры

&НаСервере
Функция ВыполнитьСервернуюПроцедуру() Экспорт
    // Создание макета отчета
    Макет = ПолучитьМакет();
    
    // Формирование отчета
    Попытка
        КомпоновщикМакет = Новый КомпоновщикМакетаКомпоновкиДанных;
        МакетКомпоновки = КомпоновщикМакет.Выполнить(СхемаКомпоновкиДанных, КомпоновщикНастроек.Настройки);
        
        ПроцессорКомпоновки = Новый ПроцессорКомпоновкиДанных;
        Результат = ПроцессорКомпоновки.Выполнить(МакетКомпоновки);
        
        ТабличныйДокумент.Очистить();
        
        ПроцессорВывода = Новый ПроцессорВыводаРезультатаКомпоновкиДанныхВТабличныйДокумент;
        ПроцессорВывода.УстановитьТабличныйДокумент(ТабличныйДокумент);
        ПроцессорВывода.Вывести(Результат);
        
        Возврат Новый Структура("Выполнено", Истина);
    Исключение
        Сообщить("Ошибка: " + ОписаниеОшибки());
        Возврат Новый Структура("Выполнено,СообщениеОбОшибке", Ложь, ОписаниеОшибки());
    КонецПопытки;
КонецФункции
            """
        }
        
        return CodeTemplate(
            metadata=metadata,
            template_content=template_content,
            validation_rules=[
                "Проверить корректность запроса СКД",
                "Проверить права на чтение данных",
                "Проверить настройки компоновщика"
            ],
            examples=[
                "Отчет по продажам с группировкой",
                "Отчет по остаткам товаров",
                "Сравнительный анализ данных"
            ]
        )
    
    def create_catalog_template(self) -> CodeTemplate:
        """Создает базовый шаблон справочника."""
        metadata = TemplateMetadata(
            name="basic_catalog",
            description="Базовый шаблон справочника с основными функциями",
            version="1.0.0",
            object_type="catalog",
            complexity_level="standard",
            author="TemplateLibrary",
            tags=["basic", "catalog", "template"]
        )
        
        template_content = {
            "module_object": """
&НаСервере
Процедура ПриЗаписи(Отказ)
    // Проверки перед записью элемента
    
    // Проверка уникальности кода
    Если НЕ ЭтоНовый() И Ссылка.Код <> Код Тогда
        Если НайтиПоКоду(Код) <> ПустаяСсылка() Тогда
            Сообщить("Элемент с таким кодом уже существует!");
            Отказ = Истина;
            Возврат;
        КонецЕсли;
    КонецЕсли;
    
    // TODO: Добавить дополнительные проверки
    
    // Аудит изменений
    ЗаписатьАудитИзменений("Запись справочника", Ссылка, Наименование);
КонецПроцедуры

&НаСервере
Процедура ОбработкаЗаполнения(ДанныеЗаполнения, ТекстЗаполнения, СтандартнаяОбработка)
    // Заполнение по умолчанию при создании нового элемента
    
    Если ТипЗнч(ДанныеЗаполнения) = Тип("Структура") Тогда
        // Заполнение из структуры
        Для Каждого Элемент Из ДанныеЗаполнения Цикл
            Если Элемент.Ключ = "Наименование" Тогда
                Наименование = Элемент.Значение;
            КонецЕсли;
            // TODO: Добавить заполнение других реквизитов
        КонецЦикла;
    КонецЕсли;
    
    // Установка значений по умолчанию
    Если ПустаяСтрока(Наименование) Тогда
        Наименование = "Новый элемент";
    КонецЕсли;
КонецПроцедуры

&НаСервере
Функция ПроверитьВозможностьУдаления() Экспорт
    // Проверка возможности удаления элемента
    
    // TODO: Добавить проверки связей с другими объектами
    // Проверка ссылочной целостности
    
    Возврат Истина;
КонецФункции

&НаСервере
Процедура ЗаписатьАудитИзменений(Действие, Объект, Значение)
    // Запись в журнал аудита (если используется)
    // TODO: Реализовать запись в систему аудита
КонецПроцедуры
            """,
            "module_manager": """
&НаСервере
Функция НайтиПоКоду(Код, ИспользоватьПоискПоКоду = Истина) Экспорт
    // Поиск элемента справочника по коду
    
    Запрос = Новый Запрос;
    Запрос.Текст = "
        |ВЫБРАТЬ ПЕРВЫЕ 1
        |    Ссылка
        |ИЗ
        |    Справочник.Номенклатура КАК Таблица
        |ГДЕ
        |    Таблица.Код = &Код
        |";
    
    Запрос.УстановитьПараметр("Код", Код);
    
    Результат = Запрос.Выполнить();
    Выборка = Результат.Выбрать();
    
    Если Выборка.Следующий() Тогда
        Возврат Выборка.Ссылка;
    Иначе
        Возврат ПустаяСсылка();
    КонецЕсли;
КонецФункции

&НаСервере
Функция ПолучитьСписокПоУсловию(Условие) Экспорт
    // Получение списка элементов по условию
    
    Запрос = Новый Запрос;
    Запрос.Текст = "
        |ВЫБРАТЬ
        |    Ссылка,
        |    Код,
        |    Наименование
        |ИЗ
        |    Справочник.Номенклатура КАК Таблица
        |ГДЕ
        |    " + Условие + "
        |УПОРЯДОЧИТЬ ПО
        |    Наименование
        |";
    
    Результат = Запрос.Выполнить();
    Возврат Результат.Выгрузить();
КонецФункции
            """
        }
        
        return CodeTemplate(
            metadata=metadata,
            template_content=template_content,
            validation_rules=[
                "Проверить уникальность кода",
                "Проверить заполненность обязательных полей",
                "Проверить корректность данных"
            ],
            examples=[
                "Справочник товаров с дополнительными реквизитами",
                "Справочник контрагентов с иерархией",
                "Классификатор с поиском по различным критериям"
            ]
        )
    
    def create_document_template(self) -> CodeTemplate:
        """Создает базовый шаблон документа."""
        metadata = TemplateMetadata(
            name="basic_document",
            description="Базовый шаблон документа с движением по регистрам",
            version="1.0.0",
            object_type="document",
            complexity_level="advanced",
            author="TemplateLibrary",
            tags=["basic", "document", "movements"]
        )
        
        template_content = {
            "module_object": """
&НаСервере
Процедура ОбработкаПроведения(Отказ, Режим)
    // Обработка проведения документа
    // Проверки перед проведением
    
    // Проверка заполненности обязательных полей
    Если ПустаяСтрока(Комментарий) Тогда
        Сообщить("Комментарий обязателен для заполнения!");
        Отказ = Истина;
        Возврат;
    КонецЕсли;
    
    // Проверка даты документа
    Если Дата < НачалоГода(ТекущаяДата()) Тогда
        Сообщить("Дата документа не может быть ранее начала года!");
        Отказ = Истина;
        Возврат;
    КонецЕсли;
    
    // TODO: Добавить проверки бизнес-логики
    
    // Создание движений по регистрам
    СоздатьДвижения();
    
    // Запись аудита
    ЗаписатьАудитПроведения();
КонецПроцедуры

&НаСервере
Процедура ОбработкаУдаленияПроведения(Отказ)
    // Обработка отмены проведения
    
    // Удаление движений по регистрам
    УдалитьДвижения();
    
    // Запись аудита
    ЗаписатьАудитОтменыПроведения();
КонецПроцедуры

&НаСервере
Процедура СоздатьДвижения()
    // Создание движений по регистрам
    
    // TODO: Добавить движения по необходимым регистрам
    // Пример для регистра сведений:
    
    Движения = Движения.РегистрСведений_Пример;
    Движение = Движения.Добавить();
    Движение.Период = Дата;
    Движение.Измерение1 = Ссылка;
    Движение.Ресурс1 = ЗначениеРесурса;
    
    // Записать движения
    Движения.Записать();
КонецПроцедуры

&НаСервере
Процедура УдалитьДвижения()
    // Удаление движений по регистрам
    
    // Удаляем движения по всем регистрам
    Движения.РегистрСведений_Пример.Очистить();
    Движения.РегистрСведений_Пример.Записать();
    
    // TODO: Добавить очистку движений по другим регистрам
КонецПроцедуры

&НаСервере
Процедура ЗаписатьАудитПроведения()
    // Запись в журнал аудита (если используется)
    // TODO: Реализовать запись в систему аудита
КонецПроцедуры

&НаСервере
Процедура ЗаписатьАудитОтменыПроведения()
    // Запись в журнал аудита (если используется)
    // TODO: Реализовать запись в систему аудита
КонецПроцедуры
            """,
            "module_form": """
&НаКлиенте
Процедура ПровестиНажатие(Кнопка)
    // Проведение документа
    
    Если Модифицированность Тогда
        Ответ = Вопрос("Документ изменен. Провести и закрыть?", РежимДиалогаВопрос.ДаНетОтмена);
        Если Ответ = КодВозвратаДиалога.Отмена Тогда
            Возврат;
        ИначеЕсли Ответ = КодВозвратаДиалога.Да Тогда
            Если НЕ Записать() Тогда
                Возврат;
            КонецЕсли;
        КонецЕсли;
    КонецЕсли;
    
    Попытка
        Провести();
        Сообщить("Документ проведен успешно");
        ОбновитьОтображениеДанных();
    Исключение
        Сообщить("Ошибка проведения: " + ОписаниеОшибки());
    КонецПопытки;
КонецПроцедуры

&НаКлиенте
Процедура ОтменитьПроведениеНажатие(Кнопка)
    // Отмена проведения документа
    
    Ответ = Вопрос("Отменить проведение документа?", РежимДиалогаВопрос.ДаНет);
    Если Ответ = КодВозвратаДиалога.Нет Тогда
        Возврат;
    КонецЕсли;
    
    Попытка
        ОтменитьПроведение();
        Сообщить("Проведение документа отменено");
        ОбновитьОтображениеДанных();
    Исключение
        Сообщить("Ошибка отмены проведения: " + ОписаниеОшибки());
    КонецПопытки;
КонецПроцедуры

&НаКлиенте
Процедура ТабличнаяЧасть1ПриИзменении(Элемент)
    // Обработчик изменений в табличной части
    // TODO: Добавить обработку изменений
КонецПроцедуры
            """
        }
        
        return CodeTemplate(
            metadata=metadata,
            template_content=template_content,
            validation_rules=[
                "Проверить заполненность обязательных реквизитов",
                "Проверить корректность даты документа",
                "Проверить корректность движений"
            ],
            examples=[
                "Документ прихода товаров",
                "Документ списания материалов",
                "Документ корректировки данных"
            ]
        )
    
    def initialize_library(self):
        """Инициализирует библиотеку базовыми шаблонами."""
        templates_to_create = [
            self.create_processing_template(),
            self.create_report_template(),
            self.create_catalog_template(),
            self.create_document_template()
        ]
        
        for template in templates_to_create:
            if not self.save_template(template):
                self.logger.error(f"Не удалось сохранить шаблон: {template.metadata.name}")
        
        self.logger.info(f"Библиотека инициализирована {len(templates_to_create)} шаблонами")
    
    def get_template_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику библиотеки."""
        total_templates = len(self._templates_cache)
        templates_by_type = {}
        templates_by_complexity = {}
        
        for template in self._templates_cache.values():
            obj_type = template.metadata.object_type
            complexity = template.metadata.complexity_level
            
            templates_by_type[obj_type] = templates_by_type.get(obj_type, 0) + 1
            templates_by_complexity[complexity] = templates_by_complexity.get(complexity, 0) + 1
        
        return {
            'total_templates': total_templates,
            'templates_by_type': templates_by_type,
            'templates_by_complexity': templates_by_complexity,
            'average_rating': sum(t.metadata.rating for t in self._templates_cache.values()) / max(total_templates, 1),
            'total_usage': sum(t.metadata.usage_count for t in self._templates_cache.values())
        }