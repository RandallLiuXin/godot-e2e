const JsonSerializer = preload("json_serializer.gd")

const VALID_QUERY_BY: Array = ["path", "name", "group", "text", "script", "type"]

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
		"find_nodes":
			return _cmd_find_nodes(cmd, id)
		"node_actionable":
			return _cmd_node_actionable(cmd, id)
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
		"hover_node":
			return _cmd_hover_node(cmd, id)
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
		"set_log_verbosity":
			return _cmd_set_log_verbosity(cmd, id)
		"set_log_buffer_size":
			return _cmd_set_log_buffer_size(cmd, id)
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


# ---------------------------------------------------------------------------
# find_nodes — multi-strategy structured query (used by Locator)
# ---------------------------------------------------------------------------

func _cmd_find_nodes(cmd: Dictionary, id) -> Dictionary:
	var query: Dictionary = cmd.get("query", {})
	if query.is_empty():
		return {"id": id, "error": "Empty query"}

	var start_path: String = cmd.get("start_path", "/root")
	var start_node = _server.get_tree().root.get_node_or_null(start_path)
	if start_node == null:
		return {"id": id, "error": "Start node not found: " + start_path}

	var predicates: Array = []
	predicates.append({"by": query.get("by", ""), "value": query.get("value", "")})
	for f in query.get("filters", []):
		predicates.append({"by": f.get("by", ""), "value": f.get("value", "")})

	for p in predicates:
		if not (p["by"] in VALID_QUERY_BY):
			return {"id": id, "error": "Unknown predicate 'by': " + str(p["by"])}

	var results: Array = []
	if not _try_seeded_walk(start_node, predicates, results):
		_walk_subtree(start_node, predicates, results)

	return {"id": id, "nodes": results}


# Look for path/group predicates we can use as a fast seed instead of walking
# the whole subtree. Returns true if a seed was used (results filled in place).
func _try_seeded_walk(start_node: Node, predicates: Array, results: Array) -> bool:
	for p in predicates:
		if p["by"] == "path":
			var target = _server.get_tree().root.get_node_or_null(String(p["value"]))
			if target != null \
					and _is_descendant_or_self(target, start_node) \
					and _matches_all(target, predicates):
				results.append(str(target.get_path()))
			return true
		if p["by"] == "group":
			var members: Array = _server.get_tree().get_nodes_in_group(String(p["value"]))
			for n in members:
				if _is_descendant_or_self(n, start_node) and _matches_all(n, predicates):
					results.append(str(n.get_path()))
			return true
	return false


func _walk_subtree(node: Node, predicates: Array, results: Array) -> void:
	if _matches_all(node, predicates):
		results.append(str(node.get_path()))
	for child in node.get_children():
		_walk_subtree(child, predicates, results)


func _is_descendant_or_self(node: Node, ancestor: Node) -> bool:
	var n = node
	while n != null:
		if n == ancestor:
			return true
		n = n.get_parent()
	return false


func _matches_all(node: Node, predicates: Array) -> bool:
	for p in predicates:
		if not _matches_predicate(node, p["by"], p["value"]):
			return false
	return true


func _matches_predicate(node: Node, by: String, value) -> bool:
	var s_value: String = String(value)
	var result: bool = false
	match by:
		"path":
			result = str(node.get_path()) == s_value
		"name":
			result = _str_match_or_eq(String(node.name), s_value)
		"group":
			result = node.is_in_group(s_value)
		"text":
			var text_val = node.get("text")
			if text_val != null:
				result = _str_match_or_eq(String(text_val), s_value)
		"script":
			var script = node.get_script()
			if script != null:
				result = script.resource_path == s_value
		"type":
			result = _node_is_type(node, s_value)
	return result


# Glob (Godot's String.match) if pattern contains * or ?, otherwise exact equality.
func _str_match_or_eq(s: String, pattern: String) -> bool:
	if "*" in pattern or "?" in pattern:
		return s.match(pattern)
	return s == pattern


# Walks the engine class hierarchy via ClassDB. Built-in classes only;
# script-defined class_name is not currently supported (could be added by
# inspecting node.get_script().get_global_name() and walking script bases).
func _node_is_type(node: Node, type_name: String) -> bool:
	var klass: String = node.get_class()
	while klass != "":
		if klass == type_name:
			return true
		klass = ClassDB.get_parent_class(klass)
	return false


# ---------------------------------------------------------------------------
# node_actionable — instant snapshot of whether a Control can receive a click
# ---------------------------------------------------------------------------

func _cmd_node_actionable(cmd: Dictionary, id) -> Dictionary:
	var path: String = cmd.get("path", "")
	var node = _server.get_tree().root.get_node_or_null(path)
	if node == null:
		return {"id": id, "error": "Node not found: " + path}

	var checks: Dictionary = {}
	var reasons: Array = []
	var is_control: bool = node is Control
	var is_node2d: bool = node is Node2D
	checks["control"] = is_control
	checks["node2d"] = is_node2d

	# Visibility: meaningful for any node that exposes is_visible_in_tree
	# (Control, Node2D, Node3D, ...). Pure Node has no visibility concept;
	# treat as always visible.
	var visible: bool = true
	if node.has_method("is_visible_in_tree"):
		visible = node.is_visible_in_tree()
	checks["visible"] = visible

	# Only Control and Node2D can be targeted by click_node / hover_node
	# (the action commands compute a screen position that's only defined for
	# those types). Other node kinds — Node3D, Window, plain Node — are
	# rejected up front so is_actionable() does not promise a click that
	# click() will refuse with "Cannot determine screen position".
	if not is_control and not is_node2d:
		reasons.append("unclickable_node_type")
		return {"id": id, "actionable": false, "checks": checks, "reasons": reasons}

	if not visible:
		reasons.append("not_visible_in_tree")

	if not is_control:
		# Node2D: visibility is the only check that applies. mouse_filter and
		# viewport-rect checks are Control-only concepts.
		var actionable_2d: bool = reasons.is_empty()
		return {"id": id, "actionable": actionable_2d, "checks": checks, "reasons": reasons}

	# Control: full check.
	var mf_ok: bool = node.mouse_filter != Control.MOUSE_FILTER_IGNORE
	checks["mouse_filter_ok"] = mf_ok
	if not mf_ok:
		reasons.append("mouse_filter_ignore")

	var viewport_rect: Rect2 = node.get_viewport_rect()
	var node_rect: Rect2 = node.get_global_rect()
	var in_viewport: bool = viewport_rect.intersects(node_rect)
	checks["in_viewport"] = in_viewport
	if not in_viewport:
		reasons.append("outside_viewport")

	var actionable: bool = reasons.is_empty()
	return {"id": id, "actionable": actionable, "checks": checks, "reasons": reasons}


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


func _cmd_hover_node(cmd: Dictionary, id) -> Dictionary:
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

	var event := InputEventMouseMotion.new()
	event.position = screen_pos
	event.global_position = screen_pos
	event.relative = Vector2.ZERO
	Input.parse_input_event(event)

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
# Log capture
# ---------------------------------------------------------------------------

func _cmd_set_log_verbosity(cmd: Dictionary, id) -> Dictionary:
	var level: String = cmd.get("level", "")
	if not _server.set_log_verbosity(level):
		# set_log_verbosity returns false either when log capture is
		# inactive or when the level string is invalid. Disambiguate via
		# the public predicate rather than reaching into _log_capture.
		if not _server.has_log_capture():
			return {"id": id, "error": "log_capture_unavailable", "message": "Log capture is not active"}
		return {"id": id, "error": "invalid_argument", "message": "level must be one of error/warning/info, got '%s'" % level}
	return {"id": id, "ok": true, "level": level}


func _cmd_set_log_buffer_size(cmd: Dictionary, id) -> Dictionary:
	var size: int = cmd.get("size", 0)
	if size < 1:
		return {"id": id, "error": "invalid_argument", "message": "size must be >= 1, got %d" % size}
	if not _server.set_log_buffer_size(size):
		return {"id": id, "error": "log_capture_unavailable", "message": "Log capture is not active"}
	return {"id": id, "ok": true, "size": size}


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
