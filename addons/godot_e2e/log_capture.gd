## Engine log capture for godot-e2e.
##
## Subclasses Logger (Godot 4.5+) to intercept push_error / push_warning /
## script runtime errors / shader errors / printerr / print, buffers them
## in a thread-safe ring, and lets automation_server drain a delta on each
## response so logs travel back to the test process via the wire protocol.
##
## CRITICAL: _log_error / _log_message run on arbitrary threads (file I/O
## thread, audio thread, etc.). All buffer mutations go through _mutex.
## Do NOT call print/push_error/push_warning inside the overrides — the
## engine routes those right back here and we deadlock or recurse forever.
extends Logger

const DEFAULT_BUFFER_SIZE: int = 200

const VERBOSITY_ERROR: int = 0
const VERBOSITY_WARNING: int = 1
const VERBOSITY_INFO: int = 2

const _VALID_LEVELS: Array[String] = ["error", "warning", "info"]

var _buffer: Array[Dictionary] = []
var _next_seq: int = 0
# Highest seq number ever evicted from the buffer. Monotonic. Used at
# drain time to compute "logs the caller missed" — naive per-drain
# counters over-report when evictions happen on entries the caller has
# already drained.
var _evicted_high_seq: int = -1
var _mutex: Mutex = Mutex.new()
var _verbosity: int = VERBOSITY_WARNING
var _max_size: int = DEFAULT_BUFFER_SIZE


# ---------------------------------------------------------------------------
# Configuration (called from main thread before / after registration)
# ---------------------------------------------------------------------------

func set_verbosity(level: int) -> void:
	_mutex.lock()
	_verbosity = clamp(level, VERBOSITY_ERROR, VERBOSITY_INFO)
	_mutex.unlock()


func set_verbosity_str(level: String) -> bool:
	if not level in _VALID_LEVELS:
		return false
	set_verbosity(parse_verbosity(level))
	return true


func get_verbosity() -> int:
	return _read_verbosity()


func set_max_size(size: int) -> void:
	if size < 1:
		return
	_mutex.lock()
	_max_size = size
	_mutex.unlock()


static func parse_verbosity(s: String) -> int:
	match s:
		"error":
			return VERBOSITY_ERROR
		"info":
			return VERBOSITY_INFO
		_:
			return VERBOSITY_WARNING


# ---------------------------------------------------------------------------
# Logger virtual overrides — called from arbitrary engine threads
# ---------------------------------------------------------------------------

func _log_error(
	function: String,
	file: String,
	line: int,
	code: String,
	rationale: String,
	_editor_notify: bool,
	error_type: int,
	_script_backtraces: Array[ScriptBacktrace]
) -> void:
	# Map ErrorType enum to our wire level.
	# ERROR_TYPE_WARNING (1) is the only "warning"; everything else is
	# treated as "error" — script and shader errors are bugs, not advice.
	var level: String
	if error_type == ERROR_TYPE_WARNING:
		if _read_verbosity() < VERBOSITY_WARNING:
			return
		level = "warning"
	else:
		level = "error"

	var msg: String = rationale if rationale != "" else code
	var entry: Dictionary = {
		"level": level,
		"message": msg,
	}
	if function != "":
		entry["function"] = function
	if file != "":
		entry["file"] = file
	if line > 0:
		entry["line"] = line
	_push(entry)


func _log_message(message: String, error: bool) -> void:
	# Only captured at info verbosity. _log_error already covers the
	# push_error/push_warning paths — _log_message is for plain print()
	# and printerr(), which are noisy at warning+ verbosities.
	if _read_verbosity() < VERBOSITY_INFO:
		return
	# Strip trailing newline that Godot appends to each line.
	var trimmed := message.strip_edges(false, true)
	if trimmed == "":
		return
	_push({
		"level": "stderr" if error else "info",
		"message": trimmed,
	})


func _read_verbosity() -> int:
	# Snapshot _verbosity under the mutex so the gate decision can't be
	# torn by a concurrent set_verbosity from the main thread. Cheap;
	# called once per logger callback fire.
	_mutex.lock()
	var v: int = _verbosity
	_mutex.unlock()
	return v


# ---------------------------------------------------------------------------
# Buffer management
# ---------------------------------------------------------------------------

func _push(entry: Dictionary) -> void:
	_mutex.lock()
	entry["_seq"] = _next_seq
	_next_seq += 1
	_buffer.append(entry)
	if _buffer.size() > _max_size:
		var to_drop := _buffer.size() - _max_size
		# The slice [0:to_drop] holds the oldest seqs (append-ordered).
		# Track the highest evicted seq so drain_since can tell whether
		# the eviction lost anything the current caller hadn't drained.
		for i in range(to_drop):
			var evicted_seq: int = _buffer[i]["_seq"]
			if evicted_seq > _evicted_high_seq:
				_evicted_high_seq = evicted_seq
		_buffer = _buffer.slice(to_drop)
	_mutex.unlock()


## Return all entries with seq > last_seq, plus the count of entries the
## caller actually missed (only counts evictions whose seqs are above the
## caller's last_seq — re-evicting entries the caller already drained
## doesn't count as "lost"). Shape:
##   {
##     "entries": Array[Dictionary],  # log entries, _seq stripped
##     "dropped": int,                # truly-lost-from-this-caller count
##     "latest_seq": int              # newest seq seen (use as next last_seq)
##   }
func drain_since(last_seq: int) -> Dictionary:
	_mutex.lock()
	var out: Array = []
	var newest: int = last_seq
	for e in _buffer:
		var seq: int = e["_seq"]
		if seq > last_seq:
			var copy: Dictionary = e.duplicate()
			copy.erase("_seq")
			out.append(copy)
			if seq > newest:
				newest = seq
	# Compute "truly lost" entries: those whose seq is above the caller's
	# watermark but were evicted before this drain. _evicted_high_seq is
	# monotonic; if it's <= last_seq the caller already drained past it.
	var lost: int = 0
	if _evicted_high_seq > last_seq:
		lost = _evicted_high_seq - last_seq
	_mutex.unlock()
	return {"entries": out, "dropped": lost, "latest_seq": newest}
