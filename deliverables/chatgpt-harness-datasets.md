Нашёл несколько действительно полезных наборов. Я бы не скачивал всё подряд: у вашего harness фактически шесть разных ML-задач, и для каждой нужны разные данные.

Самые интересные находки — HelpSteer2, REPA, FollowBench, Mind2Web, WebLINX и Unicode 18.0.0. Дополнительно есть свежий SAID RAG Evaluation Benchmark 2026, в котором присутствует отдельная метрика Specificity.

# 1. Датасеты по направлениям

## A. Скоринг конкретности и качества ответов

Это наиболее перспективное направление для использования готовых размеченных данных.

[Free Nvidia Logo in All Formats, EPS, SVG, PNG...](https://images.openai.com/static-rsc-4/jus8r5MRJ4KMU9oSQMpOp_0fsKSEnjo1ea2cFlKdKBfn3zaRpXCKAjVgA01dQ8ozIv6_V9raoGyKapmkkGits3HE_q4ocFxZAkDeKmPAAdWseaHbAQB5LmGRnv_3dWZWL4LiLuvaZULOmI1xh9qcZ3qlXrIbPbwFB_n9HPwUyRo?purpose=inline)

1\. HelpSteer2

Приоритет P0

21 362 примера · English · CC BY 4.0

[Hugging Face: nvidia/HelpSteer2](https://huggingface.co/datasets/nvidia/HelpSteer2?utm_source=chatgpt.com)

Датасет NVIDIA для обучения reward-моделей. Содержит пользовательский запрос, ответ модели и пять оценок от людей по шкале 0–4:

- Helpfulness — полезность.
- Correctness — корректность.
- Coherence — связность.
- Complexity — сложность содержания.
- Verbosity — подробность ответа.

20 324 записи в train и 1 038 в validation. Каждая запись оценивалась несколькими аннотаторами.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face+1



Применение: обучить начальную модель оценки подробности, полезности и качества ответа. Использовать как основу для собственного Specificity Scorer.

[HSE logo — Berlin Graduate School of Social Science](https://images.openai.com/static-rsc-4/CmEUEBNunlpLl5NaMKAJp3CXMbCN17ngewM6b-qxhB39tJoHqiaWiPWQ0IH2huBAptyM4L6sXATIVvmGblU55z0JC5vErBojwF2HljoxgHiRjq98sIFw7i2QPNhZHxSZHWa90N-6L2GWJnByG1H7pYbF2Yr0zjeFB2sJ7Hzmku8?purpose=inline)

2\. REPA

Приоритет P0

Около 1 000 запросов · Russian · MIT

[Hugging Face: RussianNLP/repa](https://huggingface.co/datasets/RussianNLP/repa?utm_source=chatgpt.com)

Очень интересная находка именно для русскоязычного harness. Создан при участии ВШЭ, SaluteDevices, University of Oslo и Toloka AI.

Содержит пары ответов шести LLM на одинаковые запросы. Разметка включает:

- Request following.
- Factuality.
- Repetition.
- Relevance.
- Fluency.
- Contradiction.
- Sudden interruption.
- Refusal.
- Overall preference.

В Hugging Face опубликовано около 3 010 строк с попарными оценками.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+1



Применение: обучение русскоязычной модели-судьи, сравнивающей два ответа. Особенно полезны метки внезапного прерывания, отказа и следования запросу.

[RAG](https://images.openai.com/static-rsc-4/R8tUQmn-WVvLNDKfXazBXnCNBp_0iOr0L2TSKlAGqvDKHugXvTbGxdnppwOnXHwD8uy3M8Nf-Pr1_IeHtubtuCPx6qg31_37rxKIJBAnwZ3FwzfwcUDddnGxb3mSKIRMQQHE_VH731Z2z8S4cu8x8eiOpKtScrwzMf_SWhpcDng?purpose=inline)

3\. SAID RAG Evaluation Benchmark 2026

Приоритет P0

240 000 ответов · English · CC BY 4.0

[Hugging Face: said-rag-eval-2026](https://huggingface.co/datasets/said-rag-eval-2026/said-rag-eval-benchmark?utm_source=chatgpt.com)

Один из самых интересных наборов для вашей задачи. Содержит ответы пяти моделей на вопросы из HotpotQA, MS MARCO, WikiQA, PubMedQA и FinQA, оценённые тремя LLM-судьями.

Всего 2,4 млн значений по метрикам:

- Specificity.
- Completeness.
- Conciseness.
- Coherence.
- Faithfulness.
- Hallucination-free.
- Answer relevancy.
- Citation quality.

Есть и отдельный файл с человеческой разметкой 720 примеров тремя аннотаторами.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+2



Ограничение: в распространяемых raw-записях нет исходных вопросов, эталонных ответов и контекста. Поэтому датасет лучше использовать для экспериментов с оценкой ответов по их содержимому, а не как готовый полноценный reward dataset.

[Follow-Bench: A Unified Motion Planning Benchmark for Socially-Aware Robot Person Following | AI Research Paper Details](https://images.openai.com/static-rsc-4/izN2hLteJkJ_zaGUWKgDfK270nKUmmXGv1dKVyLdU2mrayB6F0UIm6lWCjnnL6NjBstM4sx8dV0veiDEXl8VXysehHF2E009aaoH-VKnxuZEnkz27T9qojvM3Jr4OSCyh-Eg7FIu9m_9mY2w_sXAqDB2avh7aQtd3k-8cK_EEVc?purpose=inline)

4\. FollowBench

Приоритет P0

1 852 примера · English и Chinese · Apache 2.0

[Hugging Face: YuxinJiang/FollowBench](https://huggingface.co/datasets/YuxinJiang/FollowBench?utm_source=chatgpt.com)

Датасет для проверки точности следования инструкциям. Выделяет пять видов ограничений:

- Content.
- Situation.
- Style.
- Format.
- Example.

Каждый сценарий усложняется последовательным добавлением новых ограничений.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+1



Применение: обучить оценщик соответствия ответа заданным требованиям и использовать для анализа полноты, структурированности и соблюдения заданного формата.

[Allen Institute for AI (AI2) | BioEngage](https://images.openai.com/static-rsc-4/bqB2qnI0uzhGEi34B7wKYd_ICPLn3mEj4QoKIdwI4HiliVp7jVVvhBDQRb3peaJxWDTw13tyyqX19NDAcpLWbLyACwsdEAzUkI8ZyfNglv7drt7B4Nfmbsqj1Q32gIuxy6-3G44C6BlBwILEgejeG-Fb6sxTBEnTpz1XeLYUzVs?purpose=inline)

5\. IFBench

Приоритет P1

58 новых тестовых ограничений + 29 обучающих · 2025

[GitHub: allenai/IFBench](https://github.com/allenai/IFBench?utm_source=chatgpt.com)

Более современное продолжение направления instruction-following evaluation. Содержит проверяемые ограничения и функции автоматической проверки. Есть отдельный вариант двухходового взаимодействия: сначала запрос, затем дополнительное ограничение к уже сформированному ответу.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



Применение: особенно интересно для тестирования вашего механизма дополнительного сообщения в уже начатом диалоге.

[OpenBMB入驻智源社区，让大模型飞入千家万户 - 智源社区](https://images.openai.com/static-rsc-4/jqIvvgA3ZIH1yrKe_Qi2usxm0kSW5tAGjVvh4bCalWzAJgK9oDmupzqi2JWvYlTkI4HxZJFO086x0iXqlcQdt699lWxCIkLihMS0Y-byMv3kYYpwkOu56g-z5fUDVGha_wsE4atVWf4bhmcPBfPrkNQvOPp6BTSsWOVG-9u7UqE?purpose=inline)

6\. UltraFeedback

Приоритет P1

64 000 примеров · English · MIT

[Hugging Face: openbmb/UltraFeedback](https://huggingface.co/datasets/openbmb/UltraFeedback?utm_source=chatgpt.com)

Набор для preference learning: инструкции, несколько вариантов ответа, правильные и неправильные ответы.

Применение: экспериментировать с попарным сравнением ответов и обучением reward-модели. Не смешивать его оценки с оценками вашего полигона без дополнительной калибровки.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face



Мой выбор для этого блока: HelpSteer2 + REPA + SAID RAG Evaluation.

Так вы получите сочетание человеческих оценок, русскоязычных попарных предпочтений и большого массива машинных оценок конкретности.

## B. Поведенческие профили моделей и классификация ответов

Здесь нужны данные, позволяющие различать нормальный ответ, избыточную осторожность, отказ и некорректное завершение.

| Датасет                                                                                     | Размер                   | Что даёт                                           | Применение                            |
| ------------------------------------------------------------------------------------------- | ------------------------ | -------------------------------------------------- | ------------------------------------- |
| [XSTest](https://huggingface.co/datasets/walledai/XSTest?utm_source=chatgpt.com)            | 450 запросов             | 250 безопасных и 200 небезопасных запросов         | Измерение избыточных отказов          |
| [OR-Bench](https://huggingface.co/datasets/bench-llm/or-bench?utm_source=chatgpt.com)       | 80,400                   | Примеры, позволяющие изучать over-refusal          | Классификатор чрезмерной осторожности |
| [WildGuardMix](https://huggingface.co/datasets/allenai/wildguardmix?utm_source=chatgpt.com) | 86,759 train, 1,725 test | Вредоносность запроса, вредоносность ответа, отказ | Классификатор типов ответов           |

Источники: XSTest&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+1

, OR-Bench&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+1

, WildGuardMix&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+1

.



Как использовать:

- XSTest — проверить, насколько модель склонна отказываться от безопасных заданий.
- OR-Bench — расширить обучающую выборку для детектирования чрезмерной осторожности.
- WildGuardMix — обучить классификатор `refusal / compliance` и оценки характера ответа.

У WildGuardMix есть условия доступа: требуется согласиться с AI2 Responsible Use Guidelines на Hugging Face.

Что эти датасеты не решат: пустые ответы из-за нестабильности провайдера, тайм-ауты, потерю содержимого при передаче. Для этого нужна собственная телеметрия по моделям и версиям интерфейса.

## C. Browser automation и управление диалогами

Здесь нашёл два особенно подходящих датасета.

[\[Agent\] Mind2Web: Towards a Generalist Agent for the Web - BloomBerry.ai](https://images.openai.com/static-rsc-4/g2uThtgNlZWwBFDmnNxo57z9d2pKax16Wbv-uFiBVD5PFaYcVTdPOBGnXdCXaTsxkSJMDEKT9dIZ5cpfGpYRKXg3JR8Otg8t3VZ5m3mVGjpEZahUdFY6sbb1UASLSyod4q3b6UOk-vj_4NcGcvLTIv52WelA6p3cGJRONbvo2mw?purpose=inline)

1\. Mind2Web

Приоритет P1

[Hugging Face: osunlp/Mind2Web](https://huggingface.co/datasets/osunlp/Mind2Web?utm_source=chatgpt.com)

Более 2 000 заданий, 137 сайтов, 31 предметная область. Есть последовательности действий человека, описание задания и информация о веб-странице.

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+1

Для вас полезен прежде всего как источник примеров:

- поиска нужного элемента;
- последовательной навигации;
- выполнения действий с веб-формами;
- восстановления контекста страницы.

Не нужно обязательно дообучать весь браузерный агент. Можно использовать данные для тестирования устойчивости навигационного слоя.

[ICML Poster WebLINX: Real-World Website Navigation with Multi-Turn Dialogue](https://images.openai.com/static-rsc-4/hSv-aS5MUdmtA3tJrep-g_qyf3DiB787sSEiZa_HzQvwt6T2MZrgaGkGtE-mjQR71TyTGtuDJB6EsQlw9TimtCQIbjtnwxpM9eBWDO-DeuQ55m3_CttfGVXcbwG-PxtSsaOLn9Jk2Wl1HJ50rt_2idmLoFGf9IDtoehu-igtvc8?purpose=inline)

2\. WebLINX

Приоритет P1

[Официальный сайт и загрузка](https://mcgill-nlp.github.io/weblinx/?utm_source=chatgpt.com)

100 000 взаимодействий, около 2 300 демонстраций, более 150 реальных сайтов. Особенность — взаимодействие с браузером в контексте многоходового диалога.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://mcgill-nlp.github.io\&sz=32)

McGill NLP+1



Полезен для:

- работы с историей диалога;
- выполнения уточняющих действий;
- связи между намерением пользователя и следующим действием в браузере;
- обучения моделей предсказания следующего действия.

Полная версия с исходными материалами довольно большая, поэтому сначала стоит использовать подготовленные train/validation/test splits.

Дополнительно стоит посмотреть [BrowserGym](https://github.com/ServiceNow/BrowserGym?utm_source=chatgpt.com). Это не отдельный обучающий датасет, а унифицированная среда для тестирования браузерных агентов. В ней есть MiniWoB, WebArena, WorkArena, WebLINX и другие бенчмарки.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



Моя рекомендация: Mind2Web использовать первым, WebLINX — если решите обучать более универсальный компонент браузерного управления.

При этом для существующего farm я бы не обучал модель навигации с нуля. Надёжные детерминированные проверки DOM, URL и ID сценариев дадут больше пользы.

## D. Unicode, нормализация и диагностика каналов

Здесь лучше не искать обычный NLP-датасет. Есть официальные тестовые корпуса Unicode, которые гораздо полезнее для вашей задачи.

Unicode 18.0.0 — Unicode Character Database

Приоритет P0

Официальные тестовые данные Unicode Consortium

[Unicode 18.0.0 UCD](https://www.unicode.org/Public/18.0.0/ucd/?utm_source=chatgpt.com)

Рекомендую скачать следующие файлы:

| Файл                    | Для чего                                           |
| ----------------------- | -------------------------------------------------- |
| `NormalizationTest.txt` | Проверка NFC/NFD/NFKC/NFKD                         |
| `GraphemeBreakTest.txt` | Границы графем                                     |
| `WordBreakTest.txt`     | Разделение слов                                    |
| `BidiTest.txt`          | Двунаправленный текст                              |
| `BidiCharacterTest.txt` | Обработка отдельных символов и последовательностей |

Это официальные тестовые наборы соответствия Unicode-алгоритмам.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://unicode.org\&sz=32)

unicode.org+1



Дополнительно:

Unicode Security Mechanisms UTS #39

[Официальная спецификация и файлы](https://www.unicode.org/reports/tr39/?utm_source=chatgpt.com)

В частности:

- `confusables.txt` — визуально похожие символы;
- `IdentifierStatus.txt` — допустимость символов в идентификаторах;
- `IdentifierType.txt` — типы символов.

[image](https://www.google.com/s2/favicons?domain=https://www.unicode.org\&sz=32)

unicode.org

Эти корпуса не предназначены для обучения LLM. Их задача — создать эталонную тестовую матрицу.

Для вашего `channel_diagnostics` предлагаю формировать собственные записи вида:

```
{
  "fixture_id": "unicode_001",
  "unicode_version": "18.0.0",
  "surface": "user_message",
  "model_id": "model_a",
  "expected_hash": "...",
  "actual_hash": "...",
  "normalization": "NFC",
  "result": "normalized"
}
```

Проверяйте отдельно исходную строку, результат передачи и отображаемую строку. Так вы сможете установить, на каком этапе произошло изменение данных.

# 2. Какие датасеты действительно нужны каждому модулю harness

Собрал итоговую матрицу, чтобы не возникло ситуации, когда огромный объём данных скачивается, но не используется.

| Модуль harness        | Основной датасет           | Вторичный источник | Нужны собственные данные    |
| --------------------- | -------------------------- | ------------------ | --------------------------- |
| Specificity Scorer    | HelpSteer2                 | SAID RAG Eval      | Да                          |
| Success Predictor     | Ваш журнал                 | HelpSteer2, REPA   | Обязательно                 |
| Response Classifier   | WildGuardMix               | XSTest, OR-Bench   | Желательно                  |
| Model Profiles        | XSTest, OR-Bench           | WildGuardMix       | Обязательно                 |
| Browser Navigation    | Mind2Web                   | WebLINX            | Желательно                  |
| Dialog Manager        | WebLINX                    | Mind2Web           | Да, для интерфейса полигона |
| Channel Diagnostics   | Unicode UCD                | UTS #39            | Обязательно                 |
| Evaluation Reconciler | Нет подходящего публичного | Нет                | Обязательно                 |
| Pending Manager       | Нет подходящего публичного | Нет                | Обязательно                 |
| Queue Manager         | Нет подходящего публичного | Нет                | Обязательно                 |

Обратите внимание на ещё один полезный датасет, особенно для русскоязычных заданий:

European IFEval — [GitHub](https://github.com/Telefonica-Scientific-Research/european-ifeval?utm_source=chatgpt.com).

Это бенчмарк на 50 европейских языках, включая русский и латышский. Содержит нормализованные тестовые JSONL-наборы и автоматический evaluator. Он проверяет выполнение инструкций с формально проверяемыми ограничениями. Методология описана в работе, принятой на INLG 2026.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



Для вашего случая это хороший способ проверить, не ухудшает ли работа с дополнительными ходами способность модели следовать первоначальным и последующим ограничениям.

# 3. Что я рекомендую скачать в первую очередь

Я бы ограничил первую загрузку следующими наборами:

## Первая партия датасетов

7 из 8 выбрано

Выбрать все

nvidia/HelpSteer2

Оценка качества и подробности ответов

RussianNLP/repa

Русскоязычная модель-судья

said-rag-eval-2026/said-rag-eval-benchmark

Specificity и completeness

YuxinJiang/FollowBench

Следование инструкциям

allenai/WildBench

Дополнительная оценка качества

osunlp/Mind2Web

Навигация браузера

walledai/XSTest

Отказы и поведенческие профили

bench-llm/or-bench

Избыточные отказы

&#x20;Скопировать список датасетов

Unicode 18.0.0 и WebLINX добавил бы отдельными загрузками, поскольку это не обычные небольшие текстовые наборы.

## 4. Команда для загрузки через Hugging Face

На вашей машине можно подготовить отдельный каталог данных:

```
pip install -U datasets huggingface_hub

mkdir -p data/raw

hf download nvidia/HelpSteer2 \
  --repo-type dataset \
  --local-dir data/raw/helpsteer2

hf download RussianNLP/repa \
  --repo-type dataset \
  --local-dir data/raw/repa

hf download YuxinJiang/FollowBench \
  --repo-type dataset \
  --local-dir data/raw/followbench

hf download allenai/WildBench \
  --repo-type dataset \
  --local-dir data/raw/wildbench

hf download walledai/XSTest \
  --repo-type dataset \
  --local-dir data/raw/xstest

hf download bench-llm/or-bench \
  --repo-type dataset \
  --local-dir data/raw/or-bench
```

Для WildGuardMix сначала потребуется принять условия доступа на Hugging Face. Для WebLINX я бы использовал загрузку подготовленного сплита через `datasets`, не скачивая сразу весь архив. Инструкция загрузки есть на [официальном сайте](https://mcgill-nlp.github.io/weblinx/?utm_source=chatgpt.com).&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Datasets at Hugging Face+2



# 5. Как именно использовать данные для обучения

Я бы не объединял всё в один SFT-датасет. Сделал бы четыре независимых обучающих набора:

```
training_data/
│
├── response_quality/
│   ├── helpsteer2.jsonl
│   ├── repa.jsonl
│   └── said_specificity.jsonl
│
├── instruction_following/
│   ├── followbench.jsonl
│   ├── ifbench.jsonl
│   └── european_ifeval.jsonl
│
├── behavior/
│   ├── xstest.jsonl
│   ├── orbench.jsonl
│   └── wildguardmix.jsonl
│
├── browser_actions/
│   ├── mind2web.jsonl
│   └── weblinx.jsonl
│
└── local_data/
    ├── harness_attempts.jsonl
    ├── evaluation_results.jsonl
    ├── channel_observations.jsonl
    └── model_profiles.jsonl
```

Мой план обучения:

| Компонент            | Алгоритм                                                                                                       |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| Specificity Scorer   | CatBoost/LightGBM или небольшая регрессионная модель на признаках; HelpSteer2 и SAID как дополнительные данные |
| Response Judge       | Pairwise reward model, REPA + UltraFeedback                                                                    |
| Behavior Classifier  | Multilabel-классификатор, XSTest + WildGuardMix + OR-Bench                                                     |
| Browser Action Model | SFT по Mind2Web/WebLINX, только при необходимости обучать агент навигации                                      |
| Success Predictor    | Логистическая регрессия на собственных размеченных попытках                                                    |
| Channel Diagnostics  | Детерминированные Unicode-тесты, без обучения LLM                                                              |

### Важное замечание по вашим 90 размеченным попыткам

Не стоит добавлять 20 тысяч записей HelpSteer2 к 90 локальным попыткам и считать, что у вас получилось 20 тысяч примеров для предиктора успешной оценки.

У HelpSteer2 и вашего оценщика разные целевые переменные.

Внешние датасеты помогут научиться измерять полезность, конкретность и подробность, но вероятность положительной оценки именно на вашем полигоне необходимо обучать на собственных результатах.

Для начала достаточно логистической регрессии на 4–6 признаках с групповым разделением по сценариям. Fine-tuning LLM пока не нужен.

## Итоговый приоритет

Мой выбор

Если бы я готовил задачу для вашего Hermes или Cursor, я поручил бы сначала скачать и подготовить HelpSteer2, REPA, SAID RAG Eval, FollowBench, Mind2Web, XSTest и OR-Bench.

Это даст материал для трёх наиболее полезных интеллектуальных компонентов harness: оценки ответов, классификации поведения моделей и анализа выполнения сценариев.

А Unicode, Reconciler и Pending Manager я бы развивал на специальных тестовых фикстурах из собственного полигона, а не пытался обучать на чужих данных.

Отдельно можно настроить ежемесячный мониторинг новых датасетов и бенчмарков для этих компонентов:

📚Ежемесячно искать новые датасетыНажмите, чтобы настроить

Настроить такой поиск на первое число каждого месяца?