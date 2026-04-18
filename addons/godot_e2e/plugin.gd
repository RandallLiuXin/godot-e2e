@tool
extends EditorPlugin

const AUTOLOAD_NAME := "AutomationServer"
const AUTOLOAD_PATH := "res://addons/godot_e2e/automation_server.gd"


func _enter_tree() -> void:
	add_autoload_singleton(AUTOLOAD_NAME, AUTOLOAD_PATH)


func _exit_tree() -> void:
	var setting := "autoload/%s" % AUTOLOAD_NAME
	if not ProjectSettings.has_setting(setting):
		return
	var value = ProjectSettings.get_setting(setting)
	if value == AUTOLOAD_PATH or value == "*" + AUTOLOAD_PATH:
		remove_autoload_singleton(AUTOLOAD_NAME)
