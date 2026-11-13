# Board profiles

One JSON object per arena board.  The runner reads board facts from here;
`hackathon.py` remains a transport only.

| Field | Meaning |
|---|---|
| `name` | File stem / CLI name (`lucky-break-payday`, `proving-ground`) |
| `board` | Human board name (`Lucky Break: Payday`) |
| `match` | URL substring used to find the tab |
| `url` | Board URL |
| `scenario_selector` | `card` (click a scenario card) or `behaviorId` (`?behaviorId=`) |
| `model_confirm` | Page text that confirms the model (`Attacking:`) |
| `win_string` | Page text that means a win (`SCENARIO SOLVED` / `Break Successful!`) |
| `cost` | `{message, judge}` cost per action |
| `scenario_titles` | Scenario id → card title |
| `card_hints` | Scenario id → card text hint |
| `mock_signs` | Scenario id → regex signatures of the mock reply |

`harness/boards.py` validates the required fields; `harness/acceptance.py`
checks that the Payday profile matches the live `lbp.py` constants.  Adding a
board means adding one JSON file and, if it has non-card selection, a selector
in the runner — not a new copy of the whole harness.