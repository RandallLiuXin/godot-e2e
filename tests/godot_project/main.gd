extends Node2D

var counter: int = 0
var player_speed: float = 200.0
var test_string: String = "Hello E2E"


func _ready() -> void:
	$Label.text = "Counter: 0"


func _process(delta: float) -> void:
	if Input.is_action_just_pressed("ui_accept"):
		counter += 1
		$Label.text = "Counter: " + str(counter)

	var player: Node2D = $Player
	if Input.is_action_pressed("ui_right"):
		player.position.x += player_speed * delta
	if Input.is_action_pressed("ui_left"):
		player.position.x -= player_speed * delta


func get_counter() -> int:
	return counter


func add_to_counter(amount: int) -> int:
	counter += amount
	$Label.text = "Counter: " + str(counter)
	return counter


func reset_counter() -> void:
	counter = 0
	$Label.text = "Counter: 0"
