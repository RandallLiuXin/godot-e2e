const JsonSerializer = preload("json_serializer.gd")

var _server


func _init(server) -> void:
	_server = server


func execute(cmd: Dictionary) -> Dictionary:
	var action: String = cmd.get("action", "")
	var id = cmd.get("id", null)

	match action:
		"node_exists":
			return _cmd_node_exists(cmd, id)
		"get_property":
			return _cmd_get_property(cmd, id)
		"set_property":
			return _cmd_set_property(cmd, id)
		"call_method":
			return _cmd_call_method(cmd, id)
		"find_by_group":
			return _cmd_find_by_group(cmd, id)
		"query_nodes":
			return _cmd_query_nodes(cmd, id)
		"get_tree":
			return _cmd_get_tree(cmd, id)
		"batch":
			return _cmd_batch(cmd, id)
		"input_key":
			return _cmd_input_key(cmd, id)
		"input_action":
			return _cmd_input_action(cmd, id)
		"input_mouse_button":
			return _cmd_input_mouse_button(cmd, id)
		"input_mouse_motion":
			return _cmd_input_mouse_motion(cmd, id)
		"click_node":
			return _cmd_click_node(cmd, id)
		"wait_process_frames":
			return _cmd_wait_process_frames(cmd, id)
		"wait_physics_frames":
			return _cmd_wait_physics_frames(cmd, id)
		"wait_seconds":
			return _cmd_wait_seconds(cmd, id)
		"wait_for_node":
			return _cmd_wait_for_node(cmd, id)
		"wait_for_signal":
			return _cmd_wait_for_signal(cmd, id)
		"wait_for_property":
			return _cmd_wait_for_property(cmd, id)
		"get_scene":
			return _cmd_get_scene(cmd, id)
		"change_scene":
			return _cmd_change_scene(cmd, id)
		"reload_scene":
			return _cmd_reload_scene(cmd, id)
		"screenshot":
			return _cmd_screenshot(cmd, id)
		"quit":
			return _cmd_quit(cmd, id)
		_:
			return {"id": id, "error": "Unknown command: " + action}


# ---------------------------------------------------------------------------
# Node Operations (instant)
# ---------------------------------------------------------------------------

func _cmd_node_exists(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var node = _server.get_tree().root.get_node_or_null(path)
	return {"id": id, "exists": node != null}


func _cmd_get_property(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var property: String = cmd.get("property", "")
	var node = _server.get_tree().root.get_node_or_null(path)
	if node == null:
		return {"id": id, "error": "Node not found: " + path}
	var value = node.get_indexed(property)
	if value == null and not property in _get_property_list_names(node):
		# Check if base property exists (before colon)
		var base_prop: String = property.split(":")[0]
		if node.get(base_prop) == null and not base_prop in _get_property_list_names(node):
			return {"id": id, "error": "Property not found: " + property + " on " + path}
	return {"id": id, "result": JsonSerializer.serialize(value)}


func _cmd_set_property(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var property: String = cmd.get("property", "")
	var raw_value = cmd.get("value")
	var node = _server.get_tree().root.get_node_or_null(path)
	if node == null:
		return {"id": id, "error": "Node not found: " + path}
	var value = JsonSerializer.deserialize(raw_value)
	node.set_indexed(property, value)
	return {"id": id, "ok": true}


func _cmd_call_method(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var method: String = cmd.get("method", "")
	var raw_args: Array = cmd.get("args", [])
	var node = _server.get_tree().root.get_node_or_null(path)
	if node == null:
		return {"id": id, "error": "Node not found: " + path}
	var args: Array = []
	for arg in raw_args:
		args.append(JsonSerializer.deserialize(arg))
	if not node.has_method(method):
		return {"id": id, "error": "Method call failed: " + method + " not found on " + path}
	var result = node.callv(method, args)
	return {"id": id, "result": JsonSerializer.serialize(result)}


func _cmd_find_by_group(cmd: Dictionary, id) -> Dictionary:
	var group: String = cmd.get("group", "")
	var nodes: Array = _server.get_tree().get_nodes_in_group(group)
	var paths: Array = []
	for node in nodes:
		paths.append(str(node.get_path()))
	return {"id": id, "nodes": paths}


func _cmd_query_nodes(cmd: Dictionary, id) -> Dictionary:
	var pattern: String = cmd.get("pattern", "")
	var group: String = cmd.get("group", "")
	var results: Array = []

	if not group.is_empty():
		var group_nodes: Array = _server.get_tree().get_nodes_in_group(group)
		if pattern.is_empty():
			for node in group_nodes:
				results.append(str(node.get_path()))
		else:
			for node in group_nodes:
				if node.name.match(pattern):
					results.append(str(node.get_path()))
	elif not pattern.is_empty():
		_walk_tree_match(_server.get_tree().root, pattern, results)

	return {"id": id, "nodes": results}


func _walk_tree_match(node: Node, pattern: String, results: Array) -> void:
	if node.name.match(pattern):
		results.append(str(node.get_path()))
	for child in node.get_children():
		_walk_tree_match(child, pattern, results)


func _cmd_get_tree(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "/root")
	var max_depth: int = cmd.get("depth", 10)
	var root_node = _server.get_tree().root.get_node_or_null(path)
	if root_node == null:
		return {"id": id, "error": "Node not found: " + path}
	var tree_data: Dictionary = _build_tree_dict(root_node, max_depth, 0)
	return {"id": id, "tree": tree_data}


func _build_tree_dict(node: Node, max_depth: int, current_depth: int) -> Dictionary:
	var result: Dictionary = {
		"name": node.name,
		"type": node.get_class(),
		"path": str(node.get_path()),
		"children": [],
	}
	if current_depth < max_depth:
		for child in node.get_children():
			result["children"].append(_build_tree_dict(child, max_depth, current_depth + 1))
	return result


func _cmd_batch(cmd: Dictionary, id) -> Dictionary:
	var commands: Array = cmd.get("commands", [])
	var results: Array = []
	for sub_cmd in commands:
		var sub_result: Dictionary = execute(sub_cmd)
		if sub_result.has("_deferred"):
			results.append({"id": sub_cmd.get("id", null), "error": "Deferred commands not supported in batch"})
		else:
			results.append(sub_result)
	return {"id": id, "results": results}


# ---------------------------------------------------------------------------
# Input Simulation (deferred)
# ---------------------------------------------------------------------------

func _cmd_input_key(cmd: Dictionary, id) -> Dictionary:
	var keycode: int = cmd.get("keycode", 0)
	var pressed: bool = cmd.get("pressed", true)
	var physical: bool = cmd.get("physical", false)

	var event := InputEventKey.new()
	if physical:
		event.physical_keycode = keycode
	else:
		event.keycode = keycode
	event.pressed = pressed

	Input.parse_input_event(event)

	return {
		"_deferred": true,
		"wait_type": "physics_frames",
		"count": 2,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_input_action(cmd: Dictionary, id) -> Dictionary:
	var action_name: String = cmd.get("action_name", "")
	var pressed: bool = cmd.get("pressed", true)
	var strength: float = cmd.get("strength", 1.0)

	var event := InputEventAction.new()
	event.action = action_name
	event.pressed = pressed
	event.strength = strength

	Input.parse_input_event(event)

	return {
		"_deferred": true,
		"wait_type": "physics_frames",
		"count": 2,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_input_mouse_button(cmd: Dictionary, id) -> Dictionary:
	var x: float = cmd.get("x", 0.0)
	var y: float = cmd.get("y", 0.0)
	var button_index: int = cmd.get("button", 1)
	var pressed: bool = cmd.get("pressed", true)

	var event := InputEventMouseButton.new()
	event.position = Vector2(x, y)
	event.global_position = event.position
	event.button_index = button_index
	event.pressed = pressed

	Input.parse_input_event(event)

	return {
		"_deferred": true,
		"wait_type": "physics_frames",
		"count": 2,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_input_mouse_motion(cmd: Dictionary, id) -> Dictionary:
	var x: float = cmd.get("x", 0.0)
	var y: float = cmd.get("y", 0.0)
	var rel_x: float = cmd.get("relative_x", 0.0)
	var rel_y: float = cmd.get("relative_y", 0.0)

	var event := InputEventMouseMotion.new()
	event.position = Vector2(x, y)
	event.global_position = event.position
	event.relative = Vector2(rel_x, rel_y)

	Input.parse_input_event(event)

	return {
		"_deferred": true,
		"wait_type": "physics_frames",
		"count": 2,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_click_node(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var node = _server.get_tree().root.get_node_or_null(path)
	if node == null:
		return {"id": id, "error": "Node not found: " + path}

	var screen_pos := Vector2.ZERO

	if node is Control:
		screen_pos = node.get_global_rect().get_center()
	elif node is Node2D:
		screen_pos = node.get_viewport_transform() * node.get_global_transform() * Vector2.ZERO
	else:
		return {"id": id, "error": "Cannot determine screen position for node: " + path}

	var press_event := InputEventMouseButton.new()
	press_event.position = screen_pos
	press_event.global_position = screen_pos
	press_event.button_index = MOUSE_BUTTON_LEFT
	press_event.pressed = true
	Input.parse_input_event(press_event)

	var release_event := InputEventMouseButton.new()
	release_event.position = screen_pos
	release_event.global_position = screen_pos
	release_event.button_index = MOUSE_BUTTON_LEFT
	release_event.pressed = false
	Input.parse_input_event(release_event)

	return {
		"_deferred": true,
		"wait_type": "physics_frames",
		"count": 2,
		"id": id,
		"response": {"id": id, "ok": true},
	}


# ---------------------------------------------------------------------------
# Frame Sync (deferred)
# ---------------------------------------------------------------------------

func _cmd_wait_process_frames(cmd: Dictionary, id) -> Dictionary:
	var count: int = cmd.get("count", 1)
	return {
		"_deferred": true,
		"wait_type": "process_frames",
		"count": count,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_wait_physics_frames(cmd: Dictionary, id) -> Dictionary:
	var count: int = cmd.get("count", 1)
	return {
		"_deferred": true,
		"wait_type": "physics_frames",
		"count": count,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_wait_seconds(cmd: Dictionary, id) -> Dictionary:
	var duration: float = cmd.get("seconds", 1.0)
	return {
		"_deferred": true,
		"wait_type": "seconds",
		"duration": duration,
		"id": id,
		"response": {"id": id, "ok": true},
	}


# ---------------------------------------------------------------------------
# Synchronization (deferred)
# ---------------------------------------------------------------------------

func _cmd_wait_for_node(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var timeout: float = cmd.get("timeout", 5.0)
	return {
		"_deferred": true,
		"wait_type": "node_exists",
		"path": path,
		"timeout": timeout,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_wait_for_signal(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var signal_name: String = cmd.get("signal_name", "")
	var timeout: float = cmd.get("timeout", 5.0)
	return {
		"_deferred": true,
		"wait_type": "signal",
		"path": path,
		"signal_name": signal_name,
		"timeout": timeout,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_wait_for_property(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var property: String = cmd.get("property", "")
	var expected = cmd.get("value")
	var timeout: float = cmd.get("timeout", 5.0)
	return {
		"_deferred": true,
		"wait_type": "property",
		"path": path,
		"property": property,
		"value": expected,
		"timeout": timeout,
		"id": id,
		"response": {"id": id, "ok": true},
	}


# ---------------------------------------------------------------------------
# Scene Management
# ---------------------------------------------------------------------------

func _cmd_get_scene(_cmd: Dictionary, id) -> Dictionary:
	var current_scene = _server.get_tree().current_scene
	if current_scene == null:
		return {"id": id, "error": "No current scene"}
	return {"id": id, "scene": current_scene.scene_file_path}


func _cmd_change_scene(cmd: Dictionary, id) -> Dictionary:
	var scene_path: String = cmd.get("scene_path", "")
	_server.get_tree().change_scene_to_file(scene_path)
	return {
		"_deferred": true,
		"wait_type": "scene_change",
		"scene_path": scene_path,
		"id": id,
		"response": {"id": id, "ok": true},
	}


func _cmd_reload_scene(_cmd: Dictionary, id) -> Dictionary:
	var current_scene = _server.get_tree().current_scene
	if current_scene == null:
		return {"id": id, "error": "No current scene to reload"}
	var scene_path: String = current_scene.scene_file_path
	_server.get_tree().change_scene_to_file(scene_path)
	return {
		"_deferred": true,
		"wait_type": "scene_change",
		"scene_path": scene_path,
		"id": id,
		"response": {"id": id, "ok": true},
	}


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

func _cmd_screenshot(cmd: Dictionary, id) -> Dictionary:
	var image: Image = _server.get_viewport().get_texture().get_image()
	if image == null:
		return {"id": id, "error": "Failed to capture screenshot"}

	var save_path: String = cmd.get("save_path", "")
	if save_path.is_empty():
		var timestamp: String = Time.get_datetime_string_from_system().replace(":", "-")
		save_path = "user://e2e_screenshots/" + timestamp + ".png"
		DirAccess.make_dir_recursive_absolute(save_path.get_base_dir())

	image.save_png(save_path)

	var abs_path: String = save_path
	if save_path.begins_with("user://") or save_path.begins_with("res://"):
		abs_path = ProjectSettings.globalize_path(save_path)

	return {"id": id, "ok": true, "path": abs_path}


# ---------------------------------------------------------------------------
# Quit
# ---------------------------------------------------------------------------

func _cmd_quit(cmd: Dictionary, id) -> Dictionary:
	var exit_code: int = cmd.get("exit_code", 0)
	_server.get_tree().quit(exit_code)
	return {"id": id, "ok": true}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

func _get_property_list_names(node: Node) -> Array:
	var names: Array = []
	for prop in node.get_property_list():
		names.append(prop["name"])
	return names
