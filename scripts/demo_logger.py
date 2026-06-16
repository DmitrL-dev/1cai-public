
"""Небольшой скрипт для демонстрации работы EventLogger."""


from cursorext import EventLogger


def main() -> None:
    logger = EventLogger(workspace_id="demo-workspace", agent_id="dev-cli")
    try:
        logger.log(
            "file_edit",
            "Обновлена документация по архитектуре",
            payload={"file": "docs/architecture/overview.md", "lines": 42},
            risks=["manual-review"],
            links=["https://github.com/example/memory-store/pull/1"],
        )
        logger.log(
            "test_run",
            "Юнит-тесты пройдены",
            payload={"suite": "core", "duration_sec": 12.4},
        )

        exported_path = logger.export_unsynced()
        print(f"Экспортировано событий: {exported_path}")
    except RuntimeError as exc:
        print(f"Нет данных для экспорта: {exc}")
    finally:
        logger.close()


if __name__ == "__main__":
    main()

