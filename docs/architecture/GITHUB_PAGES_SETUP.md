# Настройка GitHub Pages для интерактивной карты

## ⚠️ Важно: Настройка репозитория

Если вы видите ошибку `Get Pages site failed`, выполните следующие шаги:

### 1. Проверьте настройки GitHub Pages

1. Перейдите в **Settings** → **Pages** вашего репозитория
2. В разделе **Source** выберите: **GitHub Actions**
3. Сохраните изменения

### 2. Проверьте права доступа

Убедитесь, что у workflow есть необходимые права:
- `contents: read` ✅
- `pages: write` ✅
- `id-token: write` ✅

### 3. Альтернативный способ (если GitHub Actions не работает)

Если деплой через GitHub Actions не работает, можно использовать деплой через ветку `gh-pages`:

```bash
# Клонируйте репозиторий
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public

# Создайте ветку gh-pages
git checkout -b gh-pages

# Скопируйте файлы
mkdir -p architecture
cp docs/architecture/interactive-architecture.html architecture/

# Закоммитьте и запушьте
git add .
git commit -m "Deploy interactive architecture map"
git push origin gh-pages
```

Затем в настройках Pages выберите:
- **Source**: `gh-pages` branch
- **Folder**: `/ (root)`

### 4. Проверка статуса

После настройки проверьте:
- Статус workflow: https://github.com/DmitrL-dev/1cai-public/actions
- Настройки Pages: https://github.com/DmitrL-dev/1cai-public/settings/pages

## 🔗 Ссылки после успешного деплоя

- Интерактивная карта: https://dmitrl-dev.github.io/1cai-public/architecture/interactive-architecture.html
- Главная страница: https://dmitrl-dev.github.io/1cai-public/

