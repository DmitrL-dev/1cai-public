# 🌍 Internationalization (i18n) Guide

**Мультиязычность в 1C AI Stack**

> ✅ **Статус:** Реализовано (RU + EN)

---

## 🎯 Поддерживаемые языки

- ✅ **Русский (RU)** — основной язык
- ✅ **English (EN)** — полный перевод
- 🚧 **Казахский (KZ)** — планируется
- 🚧 **Украинский (UK)** — планируется
- 🚧 **Белорусский (BY)** — планируется

---

## 📁 Структура файлов

```
locales/
├── ru.json    # Русский перевод
├── en.json    # English translation
├── kz.json    # Казахский (будущее)
└── uk.json    # Украинский (будущее)
```

### Формат файла перевода:

```json
{
  "bot": {
    "welcome": {
      "greeting": "👋 Привет, {name}!",
      "intro": "Я — AI-помощник для 1С разработчиков."
    }
  },
  "common": {
    "yes": "Да",
    "no": "Нет"
  }
}
```

**Вложенность:** до 3-4 уровней  
**Параметры:** через `{param_name}`

---

## 🔧 Использование в коде

### Python (Backend):

```python
from src.services.i18n_service import t, Language

# Простой перевод
message = t("bot.welcome.greeting", name="Иван")
# RU: "👋 Привет, Иван!"

# С указанием языка
message_en = t("bot.welcome.greeting", language=Language.EN, name="John")
# EN: "👋 Hello, John!"

# Вложенные ключи
error = t("bot.errors.generic", error="Connection failed")
```

### TypeScript (Frontend):

```typescript
import { useTranslation } from '@/hooks/useTranslation';

function MyComponent() {
  const { t, language, setLanguage } = useTranslation();
  
  return (
    <div>
      <h1>{t('bot.welcome.greeting', { name: 'John' })}</h1>
      <button onClick={() => setLanguage('en')}>English</button>
    </div>
  );
}
```

---

## 🎨 Добавление нового языка

### Шаг 1: Создать файл перевода

```bash
# Копируем базовый файл
cp locales/ru.json locales/kz.json
```

### Шаг 2: Перевести ключи

```json
{
  "bot": {
    "welcome": {
      "greeting": "👋 Сәлем, {name}!",
      "intro": "Мен 1С әзірлеушілері үшін AI-көмекшісімін."
    }
  }
}
```

### Шаг 3: Добавить язык в enum

```python
# src/services/i18n_service.py

class Language(str, Enum):
    RU = "ru"
    EN = "en"
    KZ = "kz"  # ← Добавить
```

### Шаг 4: Перезапустить сервисы

```bash
# Перезагрузить переводы
i18n_service.reload_translations()

# Или перезапустить приложение
docker-compose restart
```

---

## 🔄 Автоматическое определение языка

### В Telegram Bot:

```python
# Определяем язык пользователя из профиля
user_language = message.from_user.language_code  # 'ru', 'en', etc.

# Используем в переводах
welcome = t("bot.welcome.greeting", 
           language=Language(user_language), 
           name=user_name)
```

### В Web UI:

```typescript
// Определяем язык браузера
const browserLang = navigator.language.slice(0, 2);  // 'ru', 'en'

// Используем как default
const { t } = useTranslation(browserLang);
```

---

## 🌐 Переключение языка

### В Telegram Bot:

**Добавить команду `/lang`:**

```python
@router.message(Command("lang"))
async def cmd_language(message: Message):
    """Выбор языка"""
    # Показать inline keyboard с языками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")
        ]
    ])
    
    await message.reply(
        "🌍 Выберите язык / Choose language:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("lang:"))
async def callback_language(callback: CallbackQuery):
    """Обработка выбора языка"""
    lang_code = callback.data.split(":")[1]
    
    # Сохранить в БД предпочтение пользователя
    # await db.set_user_language(callback.from_user.id, lang_code)
    
    await callback.answer(
        t("common.success", language=Language(lang_code))
    )
```

### В Web UI:

```typescript
// Language selector component
function LanguageSelector() {
  const { language, setLanguage } = useTranslation();
  
  return (
    <select value={language} onChange={(e) => setLanguage(e.target.value)}>
      <option value="ru">🇷🇺 Русский</option>
      <option value="en">🇬🇧 English</option>
    </select>
  );
}
```

---

## 🧪 Тестирование переводов

### Проверка всех ключей:

```python
from src.services.i18n_service import get_i18n_service, Language

i18n = get_i18n_service()

# Проверка что все ключи переведены
def validate_translations():
    ru_keys = get_all_keys(i18n.translations['ru'])
    en_keys = get_all_keys(i18n.translations['en'])
    
    # Ключи только в RU
    missing_en = ru_keys - en_keys
    if missing_en:
        print(f"Missing EN translations: {missing_en}")
    
    # Ключи только в EN  
    missing_ru = en_keys - ru_keys
    if missing_ru:
        print(f"Missing RU translations: {missing_ru}")

validate_translations()
```

### Unit тесты:

```python
def test_i18n_service():
    i18n = get_i18n_service()
    
    # Test RU
    assert i18n.t("common.yes") == "Да"
    
    # Test EN
    assert i18n.t("common.yes", language=Language.EN) == "Yes"
    
    # Test параметры
    assert i18n.t("bot.welcome.greeting", name="Test") == "👋 Привет, Test!"
    
    # Test fallback
    assert "[missing.key]" in i18n.t("missing.key")
```

---

## 📊 Статистика языков

### Tracking:

```python
# В БД храним предпочтения пользователей
user_languages = {
    "ru": 750,  # 75%
    "en": 200,  # 20%
    "kz": 50    # 5%
}

# Analytics
total = sum(user_languages.values())
for lang, count in user_languages.items():
    percent = count / total * 100
    print(f"{lang}: {percent:.1f}%")
```

**Это помогает:**
- Понять какие языки приоритетны
- Распределить ресурсы на переводы
- Выявить проблемы с локализацией

---

## 🎯 Best Practices

### 1. Используйте ключи, а не хардкод:

❌ **Плохо:**
```python
await message.reply("Привет!")
```

✅ **Хорошо:**
```python
await message.reply(t("bot.welcome.greeting"))
```

### 2. Группируйте логически:

```json
{
  "bot": {
    "commands": { ... },
    "errors": { ... }
  },
  "api": { ... },
  "ui": { ... }
}
```

### 3. Параметры вместо конкатенации:

❌ **Плохо:**
```python
message = "Найдено: " + str(count) + " результатов"
```

✅ **Хорошо:**
```python
message = t("bot.results.search_title", count=count)
```

### 4. Fallback на default язык:

```python
# Если перевод не найден - используется RU
t("some.missing.key")  # → RU версия или [some.missing.key]
```

### 5. Консистентность иконок:

```json
{
  "bot.commands.search.description": "🔍 семантический поиск",
  "bot.commands.generate.description": "💻 генерация кода"
}
```

**Используйте одни и те же иконки в RU и EN!**

---

## 🚀 Roadmap i18n

### Q1 2025:
- [x] Базовая структура i18n
- [x] RU + EN переводы
- [ ] Автоопределение языка
- [ ] Команда /lang в боте
- [ ] Хранение предпочтений в БД

### Q2 2025:
- [ ] Казахский (KZ)
- [ ] Украинский (UK)
- [ ] Белорусский (BY)
- [ ] Интерфейс на нескольких языках

### Q3 2025:
- [ ] 10+ языков
- [ ] Community переводы
- [ ] Translation management UI
- [ ] Auto-translation через AI

---

## 💬 Как помочь с переводами

**Хотите добавить свой язык?**

1. Форкните проект
2. Создайте `locales/xx.json` (xx = код языка)
3. Переведите все ключи
4. Создайте Pull Request

**Награда:**
- ⭐ Mention в README
- 🎁 Premium подписка бесплатно на год
- 💎 Badge "Contributor" в боте

---

## 📞 Контакты

**Вопросы по i18n:**
- GitHub: [Issues](https://github.com/DmitrL-dev/1cai-public/issues) с тегом `i18n`
- Discussions: [GitHub Discussions](https://github.com/DmitrL-dev/1cai-public/discussions)

---

**Версия:** 1.0  
**Дата:** 2024-11-05  
**Статус:** ✅ Production Ready (RU + EN)

