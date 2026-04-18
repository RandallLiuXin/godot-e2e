## Main Autoload TCP server for godot-e2e.
##
## Non-blocking state machine that accepts a single TCP connection,
## authenticates via a hello/token handshake, and dispatches commands
## to command_handler.gd.
extends Node

const Config = preload("config.gd")
const CommandHandlerScript = preload("command_handler.gd")

var _handler = null

const SERVER_VERSION := "1.1.0"

enum State {
	LISTENING,
	IDLE,
	EXECUTING,
	WAITING,
	DISCONNECTED,
}

enum WaitType {
	NONE,
	PROCESS_FRAMES,
	PHYSICS_FRAMES,
	SECONDS,
	NODE_EXISTS,
	SIGNAL_EMITTED,
	PROPERTY_VALUE,
	SCENE_CHANGE,
}

# --- Networking ---
var _server: TCPServer = null
var _peer: StreamPeerTCP = null
var _recv_buffer: PackedByteArray = PackedByteArray()

# --- State machine ---
var _state: State = State.DISCONNECTED
var _authenticated: bool = false

# --- Pending command tracking ---
var _pending_id = null  # command id for the in-flight wait

# --- Wait state ---
var _wait_type: WaitType = WaitType.NONE
var _wait_process_remaining: int = 0
var _wait_physics_remaining: int = 0
var _wait_seconds_target: float = 0.0
var _wait_seconds_elapsed: float = 0.0
var _wait_node_path: String = ""
var _wait_signal_emitted: bool = false
var _wait_signal_connection: Callable = Callable()
var _wait_signal_source: Object = null
var _wait_signal_name: String = ""
var _wait_property_node_path: String = ""
var _wait_property_name: String = ""
var _wait_property_value = null
var _wait_scene_path: String = ""
var _wait_timeout_ms: int = 0
var _wait_start_ms: int = 0

# --- Physics frame counter ---
var _physics_frame_counter: int = 0


func _ready() -> void:
	if not Config.is_enabled():
		set_process(false)
		set_physics_process(false)
		return

	_handler = CommandHandlerScript.new(self)

	_server = TCPServer.new()
	var port := Config.get_port()

	if port == 0:
		port = _listen_random_port()
		if port == -1:
			return
	else:
		var err := _server.listen(port)
		if err != OK:
			push_error("godot-e2e: failed to listen on port %d (error %d)" % [port, err])
			set_process(false)
			set_physics_process(false)
			return

	var port_file := Config.get_port_file()
	if port_file != "":
		_write_port_file(port_file, port)

	_state = State.LISTENING
	_log("server listening on port %d" % port)


func _process(delta: float) -> void:
	match _state:
		State.LISTENING:
			_poll_listening()
		State.IDLE:
			_poll_connection_health()
			if _state == State.DISCONNECTED:
				return
			_poll_recv()
		State.WAITING:
			_poll_connection_health()
			if _state == State.DISCONNECTED:
				return
			_poll_wait(delta)
		State.DISCONNECTED:
			_handle_disconnect()


func _physics_process(_delta: float) -> void:
	_physics_frame_counter += 1
	if _state == State.WAITING and _wait_type == WaitType.PHYSICS_FRAMES:
		_wait_physics_remaining -= 1
		if _wait_physics_remaining <= 0:
			_send_response({"id": _pending_id, "ok": true})
			_transition_idle()


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------

func _poll_listening() -> void:
	if _server == null:
		return
	if _server.is_connection_available():
		_peer = _server.take_connection()
		_recv_buffer = PackedByteArray()
		_authenticated = false
		_state = State.IDLE
		_log("client connected")


func _poll_connection_health() -> void:
	if _peer == null:
		_state = State.DISCONNECTED
		return
	_peer.poll()
	var status := _peer.get_status()
	if status != StreamPeerTCP.STATUS_CONNECTED:
		_log("connection lost (status %d)" % status)
		_state = State.DISCONNECTED


func _poll_recv() -> void:
	var available := _peer.get_available_bytes()
	if available > 0:
		var result := _peer.get_data(available)
		var error: int = result[0]
		var data: PackedByteArray = result[1]
		if error != OK:
			_log("recv error %d" % error)
			_state = State.DISCONNECTED
			return
		_recv_buffer.append_array(data)

	# Extract complete length-prefixed messages.
	while true:
		if _recv_buffer.size() < 4:
			break
		var msg_len := _decode_u32_be(_recv_buffer, 0)
		if _recv_buffer.size() < 4 + msg_len:
			break
		var payload := _recv_buffer.slice(4, 4 + msg_len)
		_recv_buffer = _recv_buffer.slice(4 + msg_len)
		var json_str := payload.get_string_from_utf8()
		var parsed = JSON.parse_string(json_str)
		if parsed == null:
			_log("invalid JSON: %s" % json_str)
			_send_response({"error": "invalid_json", "message": "Could not parse JSON"})
			continue
		if parsed is not Dictionary:
			_send_response({"error": "invalid_message", "message": "Expected JSON object"})
			continue
		_dispatch(parsed)
		# After dispatch we may have entered WAITING; stop reading if so.
		if _state != State.IDLE:
			break


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------

func _send_response(data: Dictionary) -> void:
	if _peer == null:
		return
	var json_str := JSON.stringify(data)
	var payload := json_str.to_utf8_buffer()
	var header := PackedByteArray()
	header.resize(4)
	var size := payload.size()
	header[0] = (size >> 24) & 0xFF
	header[1] = (size >> 16) & 0xFF
	header[2] = (size >> 8) & 0xFF
	header[3] = size & 0xFF
	_peer.put_data(header)
	_peer.put_data(payload)
	_log(">> %s" % json_str)


static func _decode_u32_be(buf: PackedByteArray, offset: int) -> int:
	return (buf[offset] << 24) | (buf[offset + 1] << 16) | (buf[offset + 2] << 8) | buf[offset + 3]


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

func _dispatch(cmd: Dictionary) -> void:
	var action: String = cmd.get("action", "")
	var cmd_id = cmd.get("id", null)

	_log("<< %s (id=%s)" % [action, str(cmd_id)])

	# Handshake must be first.
	if not _authenticated:
		if action != "hello":
			_send_response({"id": cmd_id, "error": "not_authenticated", "message": "First command must be 'hello'"})
			_disconnect_peer()
			return
		_handle_hello(cmd)
		return

	# Delegate to command handler.
	var result: Dictionary = _handler.execute(cmd)

	if result.has("_deferred"):
		_enter_wait(result)
	else:
		_send_response(result)


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------

func _handle_hello(cmd: Dictionary) -> void:
	var cmd_id = cmd.get("id", null)
	var token: String = cmd.get("token", "")
	var expected_token := Config.get_token()

	if expected_token != "" and token != expected_token:
		_send_response({"id": cmd_id, "error": "auth_failed", "message": "Token mismatch"})
		_disconnect_peer()
		return

	_authenticated = true
	var version_info := Engine.get_version_info()
	var godot_version := "%d.%d.%d" % [version_info["major"], version_info["minor"], version_info["patch"]]
	_send_response({
		"id": cmd_id,
		"ok": true,
		"godot_version": godot_version,
		"server_version": SERVER_VERSION,
	})
	_log("authenticated")


# ---------------------------------------------------------------------------
# Wait state management
# ---------------------------------------------------------------------------

func _enter_wait(params: Dictionary) -> void:
	_pending_id = params.get("id", null)
	_state = State.WAITING
	_wait_start_ms = Time.get_ticks_msec()
	# Timeout comes as seconds from command_handler; convert to ms.
	# 0 means no timeout (used for frame waits, second waits, input settle).
	var timeout_sec: float = params.get("timeout", 0.0)
	_wait_timeout_ms = int(timeout_sec * 1000.0)

	var wait_type_str: String = params.get("wait_type", "")
	match wait_type_str:
		"process_frames":
			_wait_type = WaitType.PROCESS_FRAMES
			_wait_process_remaining = params.get("count", 1)
		"physics_frames":
			_wait_type = WaitType.PHYSICS_FRAMES
			_wait_physics_remaining = params.get("count", 1)
		"seconds":
			_wait_type = WaitType.SECONDS
			_wait_seconds_elapsed = 0.0
			_wait_seconds_target = params.get("duration", 1.0)
		"node_exists":
			_wait_type = WaitType.NODE_EXISTS
			_wait_node_path = params.get("path", "")
		"signal":
			_wait_type = WaitType.SIGNAL_EMITTED
			_wait_signal_emitted = false
			var source_path: String = params.get("path", "")
			var sig_name: String = params.get("signal_name", "")
			var source := get_tree().root.get_node_or_null(source_path)
			if source == null:
				_send_response({"id": _pending_id, "error": "node_not_found", "message": "Signal source '%s' not found" % source_path})
				_transition_idle()
				return
			_wait_signal_source = source
			_wait_signal_name = sig_name
			_wait_signal_connection = func(): _wait_signal_emitted = true
			if source.has_signal(sig_name):
				source.connect(sig_name, _wait_signal_connection, CONNECT_ONE_SHOT)
			else:
				_send_response({"id": _pending_id, "error": "signal_not_found", "message": "Signal '%s' not found on '%s'" % [sig_name, source_path]})
				_transition_idle()
				return
		"property":
			_wait_type = WaitType.PROPERTY_VALUE
			_wait_property_node_path = params.get("path", "")
			_wait_property_name = params.get("property", "")
			_wait_property_value = params.get("value")
		"scene_change":
			_wait_type = WaitType.SCENE_CHANGE
			_wait_scene_path = params.get("scene_path", "")
		_:
			_send_response({"id": _pending_id, "error": "unknown_wait_type", "message": "Unknown wait type '%s'" % wait_type_str})
			_transition_idle()


func _poll_wait(delta: float) -> void:
	# Check wall-clock timeout for all wait types.
	if _wait_timeout_ms > 0:
		var elapsed_ms := Time.get_ticks_msec() - _wait_start_ms
		if elapsed_ms >= _wait_timeout_ms:
			_send_response({"id": _pending_id, "error": "timeout", "message": "Wait timed out after %d ms" % _wait_timeout_ms})
			_cleanup_wait()
			_transition_idle()
			return

	match _wait_type:
		WaitType.PROCESS_FRAMES:
			_wait_process_remaining -= 1
			if _wait_process_remaining <= 0:
				_send_response({"id": _pending_id, "ok": true})
				_transition_idle()
		WaitType.SECONDS:
			_wait_seconds_elapsed += delta
			if _wait_seconds_elapsed >= _wait_seconds_target:
				_send_response({"id": _pending_id, "ok": true})
				_transition_idle()
		WaitType.NODE_EXISTS:
			var node := get_tree().root.get_node_or_null(_wait_node_path)
			if node != null:
				_send_response({"id": _pending_id, "ok": true})
				_transition_idle()
		WaitType.SIGNAL_EMITTED:
			if _wait_signal_emitted:
				_send_response({"id": _pending_id, "ok": true})
				_transition_idle()
		WaitType.PROPERTY_VALUE:
			var node := get_tree().root.get_node_or_null(_wait_property_node_path)
			if node != null and node.get(_wait_property_name) == _wait_property_value:
				_send_response({"id": _pending_id, "ok": true})
				_transition_idle()
		WaitType.SCENE_CHANGE:
			var current_scene := get_tree().current_scene
			if current_scene != null:
				var scene_file := current_scene.scene_file_path
				if _wait_scene_path == "" or scene_file == _wait_scene_path:
					_send_response({"id": _pending_id, "ok": true})
					_transition_idle()
		WaitType.PHYSICS_FRAMES:
			# Handled in _physics_process.
			pass


func _transition_idle() -> void:
	_cleanup_wait()
	_state = State.IDLE
	_pending_id = null
	_wait_type = WaitType.NONE


func _cleanup_wait() -> void:
	# Disconnect any pending signal connections.
	if _wait_type == WaitType.SIGNAL_EMITTED and _wait_signal_source != null:
		if not _wait_signal_emitted and _wait_signal_source.is_connected(_wait_signal_name, _wait_signal_connection):
			_wait_signal_source.disconnect(_wait_signal_name, _wait_signal_connection)
		_wait_signal_source = null
		_wait_signal_connection = Callable()
		_wait_signal_name = ""


# ---------------------------------------------------------------------------
# Disconnect / reset
# ---------------------------------------------------------------------------

func _disconnect_peer() -> void:
	if _peer != null:
		_peer.disconnect_from_host()
		_peer = null
	_state = State.DISCONNECTED


func _handle_disconnect() -> void:
	_cleanup_wait()
	_peer = null
	_recv_buffer = PackedByteArray()
	_authenticated = false
	_pending_id = null
	_wait_type = WaitType.NONE
	_state = State.LISTENING
	_log("reset to LISTENING")


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

func _listen_random_port() -> int:
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	for i in range(100):
		var candidate := rng.randi_range(10000, 60000)
		if _server.listen(candidate) == OK:
			return candidate
	push_error("godot-e2e: failed to find a free port after 100 attempts")
	set_process(false)
	set_physics_process(false)
	return -1


func _write_port_file(path: String, port: int) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("godot-e2e: failed to write port file '%s' (error %d)" % [path, FileAccess.get_open_error()])
		return
	file.store_string(str(port))
	file.close()
	_log("wrote port %d to '%s'" % [port, path])


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

func _log(msg: String) -> void:
	if Config.is_logging():
		print("[godot-e2e] %s" % msg)
