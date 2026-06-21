import { useRef, useCallback } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import { BSL_LANGUAGE_ID, bslLanguageConfig, bslTokensProvider } from '../lib/bsl-language';

interface BslEditorProps {
  value?: string;
  onChange?: (value: string | undefined) => void;
  readOnly?: boolean;
  height?: string;
}

const DEFAULT_BSL_CODE = `// 1C:Enterprise BSL Module
// Модуль обработки

#Область ПрограммныйИнтерфейс

Процедура ОбработатьДанные(Данные) Экспорт
    
    Если Данные = Неопределено Тогда
        Сообщить("Данные не заполнены");
        Возврат;
    КонецЕсли;
    
    Для Каждого Элемент Из Данные Цикл
        // Обработка элемента
        Результат = ОбработатьЭлемент(Элемент);
        
        Если НЕ Результат.Успех Тогда
            Сообщить("Ошибка: " + Результат.Описание);
        КонецЕсли;
    КонецЦикла;
    
КонецПроцедуры

Функция ОбработатьЭлемент(Элемент)
    
    Попытка
        Результат = Новый Структура("Успех, Описание", Истина, "");
        // RENTGEN-GUARD: add project-specific processing after validation.
        Возврат Результат;
    Исключение
        Возврат Новый Структура("Успех, Описание", Ложь, ОписаниеОшибки());
    КонецПопытки;
    
КонецФункции

#КонецОбласти
`;

let bslRegistered = false;

export function BslEditor({ value, onChange, readOnly = false, height = '100%' }: BslEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;

    if (!bslRegistered) {
      monaco.languages.register({ id: BSL_LANGUAGE_ID, extensions: ['.bsl', '.os'] });
      monaco.languages.setLanguageConfiguration(BSL_LANGUAGE_ID, bslLanguageConfig);
      monaco.languages.setMonarchTokensProvider(BSL_LANGUAGE_ID, bslTokensProvider);

      // BSL dark theme
      monaco.editor.defineTheme('bsl-dark', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          { token: 'keyword', foreground: '569CD6', fontStyle: 'bold' },
          { token: 'keyword.preprocessor', foreground: 'C586C0' },
          { token: 'support.function', foreground: 'DCDCAA' },
          { token: 'comment', foreground: '6A9955' },
          { token: 'string', foreground: 'CE9178' },
          { token: 'number', foreground: 'B5CEA8' },
          { token: 'number.date', foreground: 'D7BA7D' },
          { token: 'operator', foreground: 'D4D4D4' },
          { token: 'identifier', foreground: '9CDCFE' },
        ],
        colors: {
          'editor.background': '#0f172a',
          'editor.foreground': '#e2e8f0',
          'editorLineNumber.foreground': '#475569',
          'editorLineNumber.activeForeground': '#94a3b8',
          'editor.selectionBackground': '#334155',
          'editor.lineHighlightBackground': '#1e293b',
        },
      });

      bslRegistered = true;
    }

    monaco.editor.setTheme('bsl-dark');
    editor.focus();
  }, []);

  return (
    <Editor
      height={height}
      defaultLanguage={BSL_LANGUAGE_ID}
      defaultValue={value ?? DEFAULT_BSL_CODE}
      onChange={onChange}
      onMount={handleMount}
      options={{
        readOnly,
        fontSize: 14,
        fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', Consolas, monospace",
        minimap: { enabled: true },
        lineNumbers: 'on',
        renderWhitespace: 'selection',
        bracketPairColorization: { enabled: true },
        guides: { bracketPairs: true, indentation: true },
        scrollBeyondLastLine: false,
        smoothScrolling: true,
        cursorBlinking: 'smooth',
        cursorSmoothCaretAnimation: 'on',
        padding: { top: 16 },
        wordWrap: 'off',
        tabSize: 4,
        insertSpaces: true,
        automaticLayout: true,
      }}
    />
  );
}
