# E2E Coverage Checklist

Generated from: `<path to the design doc / feature list this maps>`
Last reconciled: `<date>`

This file is the contract between the design doc and the test suite. Every
player-facing feature in the doc gets exactly one row; every row maps to one
test file. A feature with no passing test is either an untested feature or a
**gap** (the doc promises behavior the game does not deliver).

## Features

| ID | Feature (observable behavior) | Scene(s) | Test file | Status |
|----|-------------------------------|----------|-----------|--------|
| F1 | Player moves right when "move_right" is held | Main | `test_player_moves_right.py` | pass |
| F2 | Score increases by 1 when a coin is collected | Main | `test_coin_increases_score.py` | pass |
| F3 | Pressing "pause" shows the pause menu | Main | `test_pause_menu.py` | gap — menu never appears |
| …  | … | … | … | … |

## Flows (playable loops)

End-to-end loops that must be reachable **through play** (not by setting
flags): start → play → win / lose / exit.

| ID | Flow | Reached state | Test file | Status |
|----|------|---------------|-----------|--------|
| L1 | Start game → collect all coins → win screen | win | `test_flow_win.py` | pass |
| L2 | Start game → take fatal damage → game-over screen | game over | `test_flow_game_over.py` | fail |
| …  | … | … | … | … |

## Status legend

- **pass** — test exists and passes; feature verified.
- **fail** — test exists but fails; could be a test bug or a real regression.
- **gap** — the observable behavior genuinely does not happen in the game;
  the doc promises it but the implementation is missing. This is the most
  valuable finding — it's an unimplemented (or broken) feature, not a test
  problem.
- **orphan** — a test file with no matching feature in the current doc.
  Delete the test, or add the feature back to the doc if it should exist.
