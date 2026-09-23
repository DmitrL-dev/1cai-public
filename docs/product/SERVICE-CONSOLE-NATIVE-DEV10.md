# Установленный Core dev10: Source Observer в отдельном процессе

24 сентября 2026 года опубликованный Core `0.1.0.dev10` проверен в консольном
режиме на Windows. Это проверка **уже выпущенного пакета**, а не новый бинарный
релиз. Verifier запустил `python -I -m rentgen_core.service_entry --console`
тремя отдельными процессами: первый цикл, повторный цикл и отказ для чужого
проекта. Исходником служил один искусственный BSL-модуль в новом каталоге на
фиксированном локальном томе.

## Как проверялась поставка

- ZIP публичного Core dev10: SHA256
  `11d5f8e850eec13d9a67c9cd1985db212a076e882b8794cb790fb7ac2dbee4e3`.
- Wheel внутри ZIP: SHA256
  `9267aed28b97644ab3d3a7c1aca3910a0945d68ddde0fcd8b84d162778ce4bc2`.
  Проверены все 92 файла пакетов `rentgen_core` и `rentgen_graph` относительно
  установленной среды. Импорты разрешились из её `site-packages`, не из checkout.
- `bsl-scan.exe` из того же ZIP: SHA256
  `8d81c1eda05d9c358385396861eb1df611d83489582f7293ad461c45017817c4`.
  Сканер скопирован в собственный каталог прогона; копия сверена побайтово.
- Текущий Windows principal зарегистрировал новый проект. Verifier создал
  отдельные registry, project state и Observer profile. Config `schema: 1` задавал
  ровно один цикл (`max_cycles: 1`) на процесс. Исходный модуль и все полные
  локальные журналы остались в приватном каталоге прогона.

## Наблюдаемый результат

| Процесс | Результат | Состояние после завершения |
| --- | --- | --- |
| Первый | Код 0, `{"status":"stopped","cycles":1}`; scanner напечатал две ожидаемые строки о стадиях работы | Один опубликованный snapshot, одна generation и один durable report типа `baseline` по одному файлу (96 байт) |
| Повторный, тот же config | Код 0, один завершённый цикл | Те же snapshot, generation, job и report; новых записей нет |
| Чужой project ID | Код 2, только `SERVICE_WORKER_FAILED` | Snapshot, generation, job, report и исходный файл не изменились |

После каждого процесса verifier смог взять и освободить Observer lease. Хэш
исходного BSL-файла остался
`037f543ff1770813d047ecc23dd2f7a8240dd74af88747084b5e39bc0a4b58df`.
Snapshot связан с актуальным source digest
`89ccd006c36d7c45e1ed105765ecafe811214a782e20cf479fbe2d78977b915f`.
Report честно содержит `model_calls: 0`, `quality: not_run`,
`business_metrics: not_available` и `source_temporal_atomicity: not_proven`.

[Машинная квитанция](evidence/service-console-native-dev10-20260924.json)
(SHA256 `3dbbb5f10cb062da10456b1b4da9113510f3840416b809edae0b3f12ba8b9c9c`)
хранит идентификаторы проекта/snapshot, контрольные суммы и счётчики без
абсолютных локальных путей. Полные stdout/stderr и входные config остались вне
Git. Сценарий воспроизводит
[`verify_service_console_native_dev10.py`](../../scripts/verification/verify_service_console_native_dev10.py):
ему нужны опубликованный ZIP dev10, извлечённый из него scanner, установленная
среда Core dev10 и **новый** `--output` на фиксированном локальном томе.

## Граница приёмки

Консольный режим проверяет установленный entrypoint, настоящий отдельный
процесс, scanner, registry и durable Observer. Этот прогон **не регистрировал
службу в Windows SCM** и не проверял `ServiceMain` под `LocalService`, права
служебной учётной записи, остановку во время работы или восстановление службы.
Он не проверял GitAuditWorker, HTTPS, внешнюю доставку уведомлений, модель,
типовую конфигурацию `.cf/.cfe`, клиентскую ИБ 1С или production deployment.
Один искусственный BSL-модуль не переносит результат на эти сценарии.

Для устройства SCM-адаптера и оставшейся приёмки см.
[SERVICE-INSTALLER.md](SERVICE-INSTALLER.md).
