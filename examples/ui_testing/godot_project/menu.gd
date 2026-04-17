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
