# UI Testing Example

Demonstrates how to test Godot UI elements with godot-e2e. Two scenes (Menu and Detail) showcase:

- **Button click testing** — click buttons via `click_node()` and verify label updates
- **Scene navigation** — navigate between scenes via button clicks
- **Scene change API** — use `change_scene()` to switch scenes directly
- **UI state verification** — read Label text and check initial/updated states

## Run

```bash
godot-e2e tests/e2e/ -v
```
