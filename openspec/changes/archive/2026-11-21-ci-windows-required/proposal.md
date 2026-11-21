## Why

Тесты на Windows три запуска подряд проходят зелёными. Пока Windows только «для сведения», поломка под Windows, где играют через установщик, проходит незаметно.

## What Changes

- В «Проверках» (`ci.yml`) убран `continue-on-error` у Windows: падение тестов на Windows — красная проверка, как на Linux.

## Capabilities

### Modified Capabilities
- `distribution`: проверки на каждый push — обязательны на обеих системах.

## Impact

- `.github/workflows/ci.yml`, `RUNBOOK.md`.
