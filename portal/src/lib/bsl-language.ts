import type { languages } from 'monaco-editor';

// BSL (Built-in Scripting Language) for 1C:Enterprise
// Keywords are bilingual: Russian + English

export const BSL_LANGUAGE_ID = 'bsl';

export const bslLanguageConfig: languages.LanguageConfiguration = {
  comments: {
    lineComment: '//',
  },
  brackets: [
    ['{', '}'],
    ['[', ']'],
    ['(', ')'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: '|', close: '|' },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
  ],
  folding: {
    markers: {
      start: /^\s*(Процедура|Функция|Если|Для|Пока|Попытка|Procedure|Function|If|For|While|Try)/i,
      end: /^\s*(КонецПроцедуры|КонецФункции|КонецЕсли|КонецЦикла|КонецПопытки|EndProcedure|EndFunction|EndIf|EndDo|EndTry)/i,
    },
  },
  indentationRules: {
    increaseIndentPattern: /^\s*(Процедура|Функция|Если|Для|Пока|Попытка|Иначе|ИначеЕсли|Procedure|Function|If|For|While|Try|Else|ElsIf)\b/i,
    decreaseIndentPattern: /^\s*(КонецПроцедуры|КонецФункции|КонецЕсли|КонецЦикла|КонецПопытки|Иначе|ИначеЕсли|EndProcedure|EndFunction|EndIf|EndDo|EndTry|Else|ElsIf)\b/i,
  },
};

export const bslTokensProvider: languages.IMonarchLanguage = {
  ignoreCase: true,
  defaultToken: '',

  keywords: [
    // Russian keywords
    'Процедура', 'КонецПроцедуры', 'Функция', 'КонецФункции',
    'Если', 'Тогда', 'ИначеЕсли', 'Иначе', 'КонецЕсли',
    'Для', 'Каждого', 'Из', 'По', 'Цикл', 'КонецЦикла',
    'Пока', 'Попытка', 'Исключение', 'КонецПопытки',
    'Возврат', 'Продолжить', 'Прервать', 'Перейти',
    'Перем', 'Новый', 'Экспорт', 'Знач',
    'И', 'Или', 'Не',
    'Истина', 'Ложь', 'Неопределено', 'NULL',
    // English keywords
    'Procedure', 'EndProcedure', 'Function', 'EndFunction',
    'If', 'Then', 'ElsIf', 'Else', 'EndIf',
    'For', 'Each', 'In', 'To', 'Do', 'EndDo',
    'While', 'Try', 'Except', 'EndTry',
    'Return', 'Continue', 'Break', 'Goto',
    'Var', 'New', 'Export', 'Val',
    'And', 'Or', 'Not',
    'True', 'False', 'Undefined',
  ],

  builtinFunctions: [
    // Russian
    'Сообщить', 'Предупреждение', 'Вопрос', 'ПоказатьВопрос',
    'Формат', 'Строка', 'Число', 'Дата', 'Булево', 'Тип', 'ТипЗнч',
    'СтрДлина', 'СтрНайти', 'СтрЗаменить', 'СтрРазделить',
    'Лев', 'Прав', 'Сред', 'ВРег', 'НРег', 'СокрЛП', 'СокрЛ', 'СокрП',
    'ТекущаяДата', 'Год', 'Месяц', 'День', 'Час', 'Минута', 'Секунда',
    'НачалоГода', 'НачалоМесяца', 'НачалоДня', 'КонецГода', 'КонецМесяца', 'КонецДня',
    'Массив', 'Структура', 'Соответствие', 'СписокЗначений', 'ТаблицаЗначений',
    'Запрос', 'РегистрСведений', 'Справочник', 'Документ',
    // English equivalents
    'Message', 'Warning', 'DoQueryBox',
    'Format', 'String', 'Number', 'Date', 'Boolean', 'Type', 'TypeOf',
    'StrLen', 'StrFind', 'StrReplace', 'StrSplit',
    'Left', 'Right', 'Mid', 'Upper', 'Lower', 'TrimAll', 'TrimL', 'TrimR',
    'CurrentDate', 'Year', 'Month', 'Day', 'Hour', 'Minute', 'Second',
    'BegOfYear', 'BegOfMonth', 'BegOfDay', 'EndOfYear', 'EndOfMonth', 'EndOfDay',
    'Array', 'Structure', 'Map', 'ValueList', 'ValueTable',
    'Query', 'InformationRegister', 'Catalog', 'Document',
  ],

  preprocessor: [
    '#Если', '#Тогда', '#ИначеЕсли', '#Иначе', '#КонецЕсли',
    '#Область', '#КонецОбласти',
    '#If', '#Then', '#ElsIf', '#Else', '#EndIf',
    '#Region', '#EndRegion',
  ],

  tokenizer: {
    root: [
      // Preprocessor
      [/#[А-Яа-яA-Za-z]+/, {
        cases: {
          '@preprocessor': 'keyword.preprocessor',
          '@default': 'identifier',
        },
      }],

      // Comments
      [/\/\/.*$/, 'comment'],

      // Strings (BSL uses "" for escaping inside strings)
      [/"([^"]*"")*[^"]*"/, 'string'],

      // Multiline strings start with |
      [/\|.*$/, 'string'],

      // Date literals
      [/'[^']*'/, 'number.date'],

      // Numbers
      [/\d+(\.\d+)?/, 'number'],

      // Identifiers and keywords
      [/[А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*/, {
        cases: {
          '@keywords': 'keyword',
          '@builtinFunctions': 'support.function',
          '@default': 'identifier',
        },
      }],

      // Operators
      [/[<>=!]+/, 'operator'],
      [/[+\-*/%]/, 'operator'],
      [/[.,;?()]/, 'delimiter'],
    ],
  },
};
