@tool
extends EditorPlugin


func _enter_tree() -> void:
	add_autoload_singleton(
		"AutomationServer",
		"res://addons/godot_e2e/automation_server.gd"
	)


func _exit_tree() -> void:
	remove_autoload_singleton("AutomationServer")
