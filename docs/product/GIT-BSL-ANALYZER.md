# BSL-LS analyzer для Git watcher

`rentgen_diagnostics.git_bsl_analyzer.BslGitAnalyzer` — read-only adapter между
`GitWatcher` и доверенным `BslLanguageServerAdapter`. Он принимает только
`GitObservation` от clean `HEAD`, перечисляет committed `.bsl/.os` через
`git ls-tree`, читает blobs через `git cat-file` и повторно проверяет тот же
HEAD после анализа. Рабочее дерево и refs не изменяются, fetch и shell не
используются.

Каждый модуль ограничен 1 MiB, общий объём — 64 MiB, число модулей — 256.
Результат BSL-LS обязан иметь совпадающие SHA/размер blob, `runtime_verified`,
полные diagnostics и completed coverage. Иначе выдаётся
`GIT_ANALYZER_INCOMPLETE`, и watcher не публикует находки. Диагностика
преобразуется в `Finding(rule="bsl/<code>", path, anchor, message, line)`;
anchor включает code и точный диапазон, что позволяет lifecycle находок
переживать изменение текста вокруг позиции.

Пример связывания:

```python
from rentgen_core.git_watcher import GitWatcher
from rentgen_diagnostics.git_bsl_analyzer import BslGitAnalyzer, PROFILE_ID, SCOPE_ID

analyzer = BslGitAnalyzer(bsl_adapter, authorize)
watcher = GitWatcher(observer, analyzer, profile_id=PROFILE_ID, scope_id=SCOPE_ID)
result = watcher.tick()
```

Для повторного опроса доступен `GitWatcherScheduler`: bounded foreground loop с
интервалом 5–86400 секунд, максимумом 10 000 циклов, backoff до 86400 секунд и
явным stop predicate. Профиль observer lock служит межпроцессным lease; ошибки
доступа, несовместимого профиля и переполнения журнала не скрываются. Scheduler
не создаёт потоков и не отправляет уведомления сам — это остаётся обязанностью
хоста службы.

Тесты `tests/unit/test_git_bsl_analyzer.py` используют настоящий Git repository
и фальшивый typed BSL adapter для проверки blob/provenance, dirty отказа,
лимитов и неполного результата. Это контрактная интеграция; полноценная native
приёмка BSL-LS на типовой конфигурации остаётся отдельным доказательством.
