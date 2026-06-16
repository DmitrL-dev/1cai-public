#!/bin/bash
# Скрипт для исправления commit messages с некорректной кодировкой
# Использует git rebase для переписывания последних N коммитов

# Исправления для последних коммитов (от старых к новым)
# Формат: HASH|OLD_MESSAGE|NEW_MESSAGE

FIXES=(
    "b94d4d4|policy & observability: добавить быстрый вход|policy & observability: add quick entry navigation"
    "82f3db0|tests: подготовить окружение и исправить базовые ошибки|tests: prepare environment and fix basic errors"
    "fd0f5bb|tests: стабилизировать окружение и заглушки для unit/integration|tests: stabilize environment and stubs for unit/integration"
    "1d328ff|ci: синхронизировать порог coverage с .coveragerc в perfect-ci-cd|ci: sync coverage threshold with .coveragerc in perfect-ci-cd"
)

echo "This script will fix commit messages with encoding issues."
echo "WARNING: This will rewrite git history!"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Note: Manual rebase is safer than automated script
echo "Please run manually:"
echo "  git rebase -i HEAD~4"
echo "Then change 'pick' to 'reword' for commits with encoding issues"
echo "and update their messages to English."

