# Установленный Core dev11: Source Observer в отдельных процессах

24 сентября 2026 года опубликованный Core `0.1.0.dev11` прошёл отдельную
проверку консольного режима Observer на Windows. Проверка запускала **установленный
пакет**, а не код из checkout, тремя процессами `python -I -m
rentgen_core.service_entry --console`: первый цикл, повторный цикл и отказ при
чужом project ID. Исходник — один искусственный BSL-модуль в новом собственном
каталоге на фиксированном локальном томе.

## Привязка к выпуску

- Публично скачанный ZIP [Core dev11](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev11):
  SHA256 `9351d2b8790a358f66931a3067e8ba1823b61b7ca6b97989bb430f8fd124441a`.
- Wheel внутри ZIP: SHA256
  `74cfe4a4f00369e13ef87c084ab1b62a016ac0661217fba015d5bccc831877b6`.
  Verifier побайтно сверил все **92 файла** `rentgen_core` и `rentgen_graph`
  с установленным wheel и проверил, что импорты идут из его `site-packages`.
- Scanner из того же ZIP: SHA256
  `8d81c1eda05d9c358385396861eb1df611d83489582f7293ad461c45017817c4`;
  собственная копия прогона совпала побайтно. Хэш Python-интерпретатора —
  `21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082`.
- Исходный BSL-модуль — 96 байт, SHA256
  `037f543ff1770813d047ecc23dd2f7a8240dd74af88747084b5e39bc0a4b58df`.
  После всех процессов полный inventory исходного дерева совпал с первоначальным.

## Наблюдаемый результат

| Процесс | Выход | Durable-состояние |
| --- | --- | --- |
| Первый | Код 0, `{"status":"stopped","cycles":1}` | Один snapshot, одна generation и один `baseline` report по одному файлу |
| Повторный с тем же config | Код 0, тот же ответ | Тот же snapshot, та же generation и один report; дубликат не появился |
| Чужой project ID | Код 2, только `SERVICE_WORKER_FAILED` | Source, snapshot, generation и report не изменились |

Observer lease освобождён после каждого процесса. Report содержит
`model_calls: 0`, `quality: not_run`, `business_metrics: not_available` и
`source_temporal_atomicity: not_proven`. SHA256 полного source inventory —
`e4920e34810c505149472d9068078953177750d5a226bc2ec7702c0c4339ae97`.
Сырые stdout/stderr, config и установленная среда сохранены локально; их хэши
сверены с [публичной квитанцией](evidence/service-console-native-dev11-20260924.json)
(2107 байт, SHA256
`d56726ec7120bb95efad825293c09cb360cd497d3172b5130826bb70e91453b2`).
Квитанция не содержит абсолютных путей хоста или SID.

## Воспроизведение и граница

За основу взят
[`verify_service_console_native_dev10.py`](../../scripts/verification/verify_service_console_native_dev10.py)
из main `6aa1199` (SHA256
`6e5ffae22b9eb9d16568ed5d022ed3943c0f436cb58f6693564338e0cf944b2a`).
Во временной копии изменены только обозначение dev10 на dev11 и корень
checkout для проверки выхода на фиксированном томе; SHA256 запущенной копии —
`b2b62187f7066af369ba76585b766222a6b673fde2d3689e0c276b82651b64f7`.
Локальный release-check helper (SHA256
`7440079086f279937607ddae527238bee9af7752e25dbeddafd4e229b8cfc339`)
адаптирует проверку ZIP, версии и всех файлов wheel для dev11. Исходные скрипты
и продуктовый пакет в Git не менялись.

Этот прогон подтвердил установленный Core в **консольном режиме**, один
синтетический модуль и локальный Observer. Служба в Windows SCM не
регистрировалась; `ServiceMain` под служебной учётной записью, остановка во
время работы и recovery службы не проверялись. Также не проверялись GitAuditWorker,
публичный HTTPS/DNS, внешняя доставка уведомлений, модель, типовая `.cf/.cfe`,
рабочая ИБ и production deployment. Один локальный хост не даёт внешней
аттестации среды.
