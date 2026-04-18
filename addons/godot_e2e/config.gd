## Command-line configuration parser for godot-e2e.
##
## Parses arguments passed after the `--` separator via OS.get_cmdline_user_args().
## Usage:
##   var cfg = preload("config.gd")
##   cfg.is_enabled()   # --e2e flag present?
##   cfg.get_port()     # --e2e-port=N (default 6008, 0 = auto)
##   cfg.get_port_file()# --e2e-port-file=PATH (write actual port here)
##   cfg.get_token()    # --e2e-token=X
##   cfg.is_logging()   # --e2e-log flag present?

class_name E2EConfig

const DEFAULT_PORT: int = 6008

static var _parsed: bool = false
static var _enabled: bool = false
static var _port: int = DEFAULT_PORT
static var _token: String = ""
static var _logging: bool = false
static var _port_file: String = ""


static func _ensure_parsed() -> void:
	if _parsed:
		return
	_parsed = true

	var args := OS.get_cmdline_user_args()
	for arg in args:
		if arg == "--e2e":
			_enabled = true
		elif arg == "--e2e-log":
			_logging = true
		elif arg.begins_with("--e2e-port="):
			var value := arg.substr("--e2e-port=".length())
			if value.is_valid_int():
				_port = value.to_int()
			else:
				push_warning("godot-e2e: invalid port value '%s', using default %d" % [value, DEFAULT_PORT])
				_port = DEFAULT_PORT
		elif arg.begins_with("--e2e-token="):
			_token = arg.substr("--e2e-token=".length())
		elif arg.begins_with("--e2e-port-file="):
			_port_file = arg.substr("--e2e-port-file=".length())


static func is_enabled() -> bool:
	_ensure_parsed()
	return _enabled


static func get_port() -> int:
	_ensure_parsed()
	return _port


static func get_token() -> String:
	_ensure_parsed()
	return _token


static func get_port_file() -> String:
	_ensure_parsed()
	return _port_file


static func is_logging() -> bool:
	_ensure_parsed()
	return _logging
