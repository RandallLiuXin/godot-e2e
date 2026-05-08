extends Control

var click_count: int = 0

func _ready():
	$VBox/ClickButton.pressed.connect(_on_click_button_pressed)
	$VBox/NavigateButton.pressed.connect(_on_navigate_button_pressed)

func _on_click_button_pressed():
	click_count += 1
	$VBox/StatusLabel.text = "Clicked " + str(click_count) + " times"

func _on_navigate_button_pressed():
	get_tree().change_scene_to_file("res://detail.tscn")

# --- Engine log capture exercise hooks ---
# These exist solely to drive integration tests in tests/e2e/test_log_capture.py
# (call them via game.call()). Keeping them on Menu rather than spinning up a
# dedicated scene keeps the example minimal.

func e2e_emit_error(msg: String) -> void:
	push_error(msg)

func e2e_emit_warning(msg: String) -> void:
	push_warning(msg)

func e2e_emit_print(msg: String) -> void:
	print(msg)

func e2e_emit_printerr(msg: String) -> void:
	printerr(msg)

func e2e_emit_many_warnings(n: int) -> void:
	# Drives the engine-side overflow accounting test by emitting a
	# pre-determined number of push_warnings inside a single command call.
	# The whole burst lands in one drain window so the response carries
	# both the truncated entries array and a non-zero _logs_dropped.
	for i in range(n):
		push_warning("BURST_%d" % i)


func e2e_trigger_runtime_error() -> void:
	# Calling a method on a null reference. GDScript reports this as a
	# script runtime error (ErrorType.SCRIPT) which our Logger captures
	# as level "error". Execution unwinds back to the caller (callv).
	#
	# We obtain null via get_node_or_null rather than `var x = null` so
	# the GDScript parser doesn't flag a "Variable is always null" warning
	# at compile time — that warning would land in stderr before our
	# Logger is registered, and isn't what this hook is meant to exercise.
	var x: Node = get_node_or_null("/nonexistent_node_for_test")
	x.queue_free()


# --- Delayed-mutation hooks for the expect() integration tests ---
# Schedule a property change after `delay` seconds (game time). The test
# kicks one of these off then immediately calls expect(...).to_*(timeout=2.0)
# and verifies the assertion polls past the delay and passes — the
# acceptance criterion for ROADMAP task 3.

func e2e_set_text_after(new_text: String, delay: float) -> void:
	var t = get_tree().create_timer(delay)
	t.timeout.connect(func(): $VBox/StatusLabel.text = new_text)


func e2e_set_counter_after(value: int, delay: float) -> void:
	var t = get_tree().create_timer(delay)
	t.timeout.connect(func(): click_count = value)


func e2e_set_button_visible_after(visible: bool, delay: float) -> void:
	var t = get_tree().create_timer(delay)
	t.timeout.connect(func(): $VBox/ClickButton.visible = visible)
