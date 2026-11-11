# Browser adapter: практический API

Этот адаптер перенесён из рабочего подхода организатора, с исправлениями: относительные пути, открытие отсутствующей вкладки, чтение настоящего значения модели, полные ответы и защита от двойной отправки. Он управляет UI браузера; API-ключ Gray Swan не нужен. Требуется Node.js 22+. Внешних npm-зависимостей нет.

Команды ниже выполняются **из папки `workspace` импортированного профиля** (Hermes использует её как рабочую папку). Например: `cd ~/.hermes/profiles/gray-swan-hackathon-v2/workspace`. Обёртка `python3 harness/hackathon.py arena …` работает с Python 3.9+ и сама находит подходящий Node.js 22+; устанавливать npm-пакеты не требуется. Все пути после `--file`, `--scope`, `--out` здесь считаются относительно этой `workspace`.

Адаптер подключается к выделенному Chrome/Chromium на `http://127.0.0.1:9223`; другой адрес задаётся `--cdp` или `HACKATHON_CDP_URL`. Альтернатива при установленном Node 22+: `node harness/engine/arena.mjs …` из той же `workspace`.

## 1. Открыть реальный Training

```sh
python3 harness/hackathon.py arena open --url https://app.grayswan.ai/training
python3 harness/hackathon.py arena tabs
python3 harness/hackathon.py arena inspect --target TARGET_ID --out arena-inspect.json
```

`open` возвращает ID вкладки. Если точный URL уже открыт — используется существующая вкладка. Иначе создаётся новая; другие вкладки и выбранные сценарии сохраняются. `open --target TARGET_ID --url URL` явно переводит указанную вкладку на другой URL того же origin. После загрузки — `inspect`. Если показан вход, участник входит в **свой** аккаунт в этом же браузере; агент не выдумывает подтверждение личности.

`inspect` читает реальные `input.value`, combobox, выбранные опции, заголовки, ссылки, поля загрузки файлов, сообщения и вердикт. Для каждого элемента возвращает CSS-selector. В текущем интерфейсе модели видны после открытия `models`; значение берётся из надписи Model → имя в настройках и/или выбранной опции, без суффикса BROKEN. Если панель закрыта и значение недоступно, откройте `models`, затем повторите чтение. Пароли и скрытые значения не читаются. Placeholder никогда не используется как подтверждённая модель.

## 2. Выбрать сценарий, модель и прочитать критерий

Из Training откройте ссылку/карточку нужного трека. URL дочернего задания может быть `/arena/challenge/proving-ground` — это само по себе **не исключает** Training. Зафиксируйте, откуда пришли: видимая ссылка/карточка из Training либо явно заданный участником Training-сценарий. Одно слово `training` в глобальном меню не доказывает принадлежность сценария.

```sh
python3 harness/hackathon.py arena select-scenario --target TARGET_ID --value EXACT_SCENARIO_ID_OR_TEXT
python3 harness/hackathon.py arena models --target TARGET_ID
python3 harness/hackathon.py arena select-model --target TARGET_ID --value 'EXACT MODEL NAME'
python3 harness/hackathon.py arena show-criteria --target TARGET_ID
python3 harness/hackathon.py arena inspect --target TARGET_ID --out arena-inspect.json
```

`models` открывает настройки и при необходимости вложенный раздел Model; возвращает актуальный снимок и `availableModels` с флагами selected/disabled/broken. Недоступные Closed-модели пропускайте. `select-model` открывает переключатель при необходимости, выбирает точное совпадение и возвращает снимок. `select-scenario` использует реальный `data-behavior-id`/`data-scenario-id` или точный видимый текст. Если UI не совпал, ошибка содержит конкретную причину; заново прочитайте `inspect`, не угадывайте кнопку.

Если модель отображается в нестандартном поле и `model.status` остаётся `unknown`/`ambiguous`, найдите в `inspect.controls` **значение** соответствующего поля. Затем:

```sh
python3 harness/hackathon.py arena context --target TARGET_ID --model-selector '#ACTUAL_MODEL_CONTROL'
```

Не подставляйте поле поиска, placeholder или название карточки из списка как уже выбранную модель. `--model-selector` должен указывать на один видимый контрол, действительно отображающий текущий выбор.

`show-criteria` сначала ищет `aria-label="View scenario criteria"`, затем кнопку `See success criteria` / `Show success criteria` / `Criteria`, если она однозначно найдена. `read --target TARGET_ID --selector 'CSS' --out criteria.json` читает полный текст указанного элемента без обрезания. Сам факт открытия критериев не запускает попытку.

## 3. Привязать точный контекст

```sh
python3 harness/hackathon.py arena bind-scope \
  --target TARGET_ID --track Chat \
  --scenario-id EXACT_SCENARIO_ID --model-id 'EXACT MODEL NAME' \
  --board 'Proving Ground' \
  --evidence-source training-link \
  --observed-context 'Переход из Training: карточка нужного трека, затем выбранный сценарий' \
  --out scope.json
```

Вместо `training-link` можно использовать `user-scenario`, если участник явно указал этот Training-сценарий; в `--observed-context` укажите это честно. `--board` — название видимой доски, оно не обязано быть буквально `Training`. Трек обязателен: `Chat`, `Image`, `Agent`, `Indirect`. При нестандартном контроле модели добавьте `--model-selector 'CSS'` и сюда.

Если платформа не раскрыла ID, `context.scenario` вернёт `id: null`, видимый заголовок и локальный `key: "title:…"`. В таком случае используйте этот key как `--scenario-id` и храните полный заголовок; это локальная идентичность, а не выдуманный серверный ID. Дубли одного заголовка в панели критериев не создают неоднозначность.

При привязке и перед каждой отправкой адаптер сверяет выбранную модель, видимый ID и сохранённый заголовок сценария, вкладку, origin и URL. После смены сценария/модели или навигации привяжите новый контекст. Если сайт поменял URL после ответа, перечитайте `context` и обновите scope перед judge. Не продолжайте со старым scope.

## 4. Одна попытка — один send и отдельный judge

Подготовьте **собственную** гипотезу и сохраните её текст в `inputs/prompt.txt`. Для текстового файла используйте папку `inputs`; для собственной нейтральной Image-проверки доступен `python3 harness/hackathon.py make-image`. Пакет не содержит выигрышных промптов и не обещает успех любой модели. Сначала убедитесь, что выбран правильный сценарий, критерий прочитан и участник дал команду на попытку.

```sh
python3 harness/hackathon.py arena send \
  --scope scope.json --file inputs/prompt.txt \
  --operation-id attempt-001-chat \
  --timeout-ms 60000 --out chat-result.json
```

`send` использует `#chatTextarea` и `#submitChatButton` из рабочего интерфейса, с однозначным запасным поиском кнопки Send. При иной разметке после `inspect` передайте `--input-selector 'CSS' --selector 'CSS_SEND_BUTTON'`. Он заполняет поле, **один раз** нажимает кнопку и ждёт нового полного ответа с ролью assistant. Нет сочетания Enter+click и скрытых повторов. `send` не нажимает Submit Break.

Для Image прикрепите собственный тестовый файл в наблюдаемый `input[type=file]`:

```sh
python3 harness/hackathon.py arena upload \
  --scope scope.json --selector '#ACTUAL_FILE_INPUT' \
  --file inputs/test-image.png
```

Для Agent/Indirect используйте фактически показанные редакторы: `fill --scope … --selector CSS --file FILE`, затем одну наблюдаемую кнопку через `click --scope … --selector CSS --operation-id ID`. Универсальный UI может отличаться по трекам; агент должен прочитать поля сценария и критерий, а не вставлять Chat-формат во все редакторы.

После ответа и проверки критерия:

```sh
python3 harness/hackathon.py arena judge \
  --scope scope.json --operation-id attempt-001-judge \
  --timeout-ms 60000 --out judge-result.json
```

`judge` один раз нажимает `#submitJailbreakButton` (при изменённой разметке можно передать `--selector CSS`) и ждёт **новый** явный результат. Он возвращает `accepted`/`rejected`, фактически наблюдаемый `submissionId`, время и текст-доказательство. Текст модели «Break Successful!» не считается вердиктом. Старая победа не повторно записывается как новая.

`pending` означает, что новый ответ/вердикт не удалось наблюдать до тайм-аута. Это не провал и не победа. Перечитайте `context`; **не отправляйте повторно**. `--operation-id` обязателен для send/judge/click; повторное использование отклоняется. Операции со scope пишутся в `workspace/attempts/browser-events.jsonl`. Это технический журнал, итог попытки отдельно запишите через навык `gray-swan-arena-attempt-tracking` вместе с треком, сценарием, моделью, гипотезой, временем и доказательством judge.

## Проверка без Arena

```sh
python3 harness/hackathon.py arena dry-run
node harness/tests/browser-fixture.test.mjs
```

Первый тест работает offline: проверяет выбор вкладки, scope, значения полей, единичные действия, тайм-ауты и защиту от старого результата. Второй запускает **отдельный headless Chrome** и локальную нейтральную HTML-страницу на 127.0.0.1; проверяет полный путь open → inspect → scope → send → judge. Он не использует аккаунт и не обращается к Arena. Если Chrome не найден, задайте `CHROME_PATH`; на Linux нужен рабочий Chrome/Chromium. Это реальная проверка транспорта и редакторов, но не утверждение, что конкретное задание Arena решено.

`help` показывает остальные команды: `read`, `wait`, `screenshot`. `--timeout-ms` принимает 1–300000 мс. Если страница изменилась, используйте актуальный `inspect` и показанные им selectors; старые ответы и «успешно кликнул» не заменяют фактический результат.
