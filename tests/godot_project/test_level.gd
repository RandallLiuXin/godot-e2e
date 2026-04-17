extends Node2D

var level_name: String = "TestLevel"
var level_id: int = 1


func get_level_info() -> String:
	return level_name + " (id: " + str(level_id) + ")"
