extends Node2D

var counter: int = 0

func _ready():
	$Label.text = "Hello godot-e2e!"

func increment() -> int:
	counter += 1
	$Label.text = "Count: " + str(counter)
	return counter
