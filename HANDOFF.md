# HANDOFF — NovaOps Intelligent RAG

## Архитектура
Корпус (handbook + eng-wiki, markdown) → чанкинг 250/50 токенов → эмбеддинги Titan v2 →
индекс `novaops-kb` в OpenSearch Serverless (k-NN). Запрос: planner (LLM выбирает subjects) →
k-NN с pre-filter → listwise reranker → отбор чанков → ответ Nova через Bedrock Converse →
оценка LLM-судьями. Детали: `docs/architecture-discovery.md`, `docs/evaluation-domain-model.md`.

## Модули
- `config.py` — загрузка `.env`, все переменные обязательны (без дефолтов).
- `client.py` — единственный владелец Bedrock runtime клиента (`bedrock`, `embed_text()`) и OpenSearch data-plane.
- `subjects.py` / `subjects.json` — словарь subjects, тэггер, кэш тэгов по статьям.
- `create_index.py` / `ingest.py` — неразрушающие: по умолчанию только проверка, запись только в пустой индекс.
- `retrieval.py` — k-NN + фильтры: audience (жёсткая безопасность, fail-closed), subjects (мягкий, fail-open), recency (выкл).
- `planner.py` — LLM-планировщик subjects (forced tool call).
- `reranker.py` — listwise rerank один раз на пул (N=10).
- `judges.py` — 4 LLM-судьи: faithfulness, context_relevance, completeness, refusal (boolean, forced tool).
- `eval.py` — 5 конфигураций, общие вызовы между ними, флаг `report` для детального отчёта.
- `models.py` — frozen Pydantic v2 модели результатов (ContentEvaluation | RefusalEvaluation по `kind`).
- `logging_setup.py` — централизованный logging; `configure_logging()` вызывается только из `eval.py main()`.
- `manage.py` — `status` / `down` (подтверждение вводом REMOVE); единственное исключение — control-plane клиент OpenSearch.

## Принятые решения
- Bedrock boundary: никакой другой модуль не создаёт `boto3.client("bedrock-runtime")`.
- Structured output только через forced tool call, temperature 0.0 для судей.
- Отбор: static top-3; dynamic — score ≥ 0.6 без fallback на top-1, иначе sentinel "not found".
- Baseline TOP_K=4; тэгирование по статьям; recency выключен.
- Отказ оценивается LLM-судьёй по всему ответу (вопрос + ответ), не по ключевым словам.
  `expect_refusal` — ожидание из датасета, `refusal_ok` — наблюдаемое поведение.
- Логи никогда не содержат промпты, ответы, текст чанков, key_facts, секреты.
- Индекс `novaops-kb` не удалять/не пересоздавать/не переиндексировать без явной просьбы.
- `.env` не коммитится; PAT из исходного README нигде не воспроизводится.

## Готово
- Все модули выше реализованы; eval.py отрабатывает на живой коллекции (exit 0).
- Refusal-судья: UNANSWERABLE_AWS → refusal_ok=True во всех 5 конфигах.
- Тесты: 224 (unittest, всё замокано, без сети; логи тестов не пишутся в `logs/`).
- Последний коммит: `b1a9343 refactor: replace refusal heuristic with LLM judge`.

## Известные проблемы
- 3 падающих теста в `tests/test_logging_setup.py` (ожидают console=INFO, file=DEBUG),
  а в `logging_setup.py` дефолты изменены на WARNING/WARNING. Нужно решить: вернуть
  дефолты или обновить тесты. Из-за WARNING INFO-строки жизненного цикла не видны в консоли.
- ACCESS_REVIEW (expect_refusal=true) → refusal_ok=False во всех конфигах: модель отвечает
  по содержимому handbook. Проверить: датасет или audience-фильтр/контент.
- Unit-тесты судей мокают модель — проверяют связку, не семантическую точность.
- Refusal-судья = +1 вызов Bedrock на refusal-вопрос × конфиг (~10 вызовов за прогон).
- `data/eval_questions_short.jsonl` застейджен (не закоммичен); в `eval.py` закомментирована
  строка `QUESTIONS_FILE` на него — решить, оставлять ли.
- Документы (`docs/architecture-discovery.md`, `docs/code-reuse-analysis.md`) могут ещё
  описывать старую эвристику `refused()` — проверить.
