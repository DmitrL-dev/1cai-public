# Воспроизводимый офлайн-комплект ядра

Сборщик `scripts/release/build_core_kit.py` включён в публичный репозиторий.
Он работает с чистым Git checkout, Windows x64, CPython 3.11 и Go 1.25.5
windows/amd64. Выходной каталог должен быть новым; существующий выпуск
сборщик не перезаписывает. Это комплект ядра и MCP, а не установщик всего продукта.

## Подготовка и сборка

В отдельном окружении CPython 3.11 подготовьте wheels двух профилей. Загрузка
требует сети; версии и допустимые SHA256 заданы в отслеживаемых lock-файлах.
Исходный манифест `requirements-rentgen.txt`, из которого формировался полный
runtime lock, также входит в checkout и sdist; lock не является единственным
непроверяемым артефактом.
Каждый wheelhouse должен содержать только пакеты своего профиля.

```powershell
py -3.11 -m venv output/kit-tools
$kitPython = (Resolve-Path output/kit-tools/Scripts/python.exe).Path
& $kitPython -m pip download --only-binary=:all: --require-hashes -r requirements/locks/mcp-py311-windows.txt --dest output/mcp-wheels
& $kitPython -m pip download --only-binary=:all: --require-hashes -r requirements/locks/product-build-py311-windows.txt --dest output/build-wheels
& $kitPython scripts/release/build_core_kit.py --output output/core-kit-dev10 --runtime-wheelhouse output/mcp-wheels --build-wheelhouse output/build-wheels --go 'C:\Program Files\Go\bin\go.exe'
```

С `--build-wheelhouse` установка инструментов сборки также использует
`--no-index`. Без этого аргумента допускается загрузка закреплённых build tools.
Go не загружает модули или другую версию toolchain. Python, Go, редактор,
Java/BSL-LS, модели и платформа 1С в комплект не входят.

Сборщик экспортирует текущий Git commit в новую папку, создаёт отдельное
окружение сборки, строит wheel и sdist. Затем распаковывает sdist в другую папку
и повторяет сборку Python и Go. Разные каталоги Go cache исключают повторное
использование первой сборки scanner. Wheel, sdist и scanner должны совпасть
побайтно. Сборщик дважды упаковывает комплект и сравнивает SHA256 ZIP.

Wheels MCP проверяются по точным идентификаторам и SHA256 выбранного профиля;
он обязан быть подмножеством полного `product-py311-windows.txt`. Недостающие,
лишние или изменённые wheels отклоняются. Это проверка закреплённых входов,
а не новый аудит CVE или независимая подпись происхождения.

## Что проверяется перед передачей

В новом окружении и отдельном профиле устанавливаются wheel ядра и SDK MCP
через `--no-index --require-hashes`, затем выполняется `pip check`.
Реальный stdio-клиент проверяет 32 MCP-команды, сохранённые исходники,
большие модули, версии черновика и архивирование/восстановление. Проверка
исключает импорт ядра из рабочего checkout. Модели и платформа 1С не вызываются.

`acceptance.json` в корне сборки содержит хэши артефактов и ссылку на подробный
отчёт офлайн-установки. `build-input-hashes.json` внутри комплекта фиксирует
Git commit, версии инструментов и хэши входов. Лицензия собственного кода — MIT;
лицензии Python-зависимостей сохранены в исходных wheels, лицензия Go приложена.

Полученный ZIP можно проверить отдельно. SHA256 берут из доверенного сообщения
о выпуске, а не из самого проверяемого архива:

```powershell
py -3.11 scripts/verification/verify_core_kit.py --kit PATH_TO_KIT.zip --output output/independent-kit-check --expected-sha256 EXPECTED_SHA256
```

Проверка сначала сверяет внешний SHA256, затем безопасные имена, типы и объёмы
архивных записей, точный состав и хэши файлов. Установка начинается после этих
проверок. Офлайн-параметры pip не являются сетевой изоляцией процесса ОС.

Этот сценарий не заменяет отдельные проверки observer, платформы, редактора,
обновлений типовых конфигураций и бизнес-тестов. Опубликованная пара раннего
доступа — [core dev10](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev10)
и [Companion 0.1.10](https://github.com/DmitrL-dev/1cai-public/releases/tag/companion-v0.1.10).
[Манифест dev10](../../releases/core/0.1.0.dev10/manifest.json) привязывает
ZIP к исходному коммиту `ef0501b`, успешному push CI и SHA256
`11d5f8e850eec13d9a67c9cd1985db212a076e882b8794cb790fb7ac2dbee4e3`.
Отдельная проверка на фиксированном локальном томе подтвердила инвентарь
40 файлов, офлайн-установку и 32 MCP-инструмента. Для dev10 также проверен
установленный ASGI wheel на локальном TLS-хосте; это не публичное развёртывание.
Предыдущая пара dev9 / 0.1.9 остаётся доступной с собственным
[манифестом](../../releases/core/0.1.0.dev9/manifest.json); её теги и файлы
не меняются.
