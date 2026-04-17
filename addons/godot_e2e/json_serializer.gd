class_name JsonSerializer


static func serialize(value: Variant) -> Variant:
	if value == null:
		return null

	match typeof(value):
		TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STRING:
			return value

		TYPE_VECTOR2:
			return {"_t": "v2", "x": value.x, "y": value.y}

		TYPE_VECTOR2I:
			return {"_t": "v2i", "x": value.x, "y": value.y}

		TYPE_VECTOR3:
			return {"_t": "v3", "x": value.x, "y": value.y, "z": value.z}

		TYPE_VECTOR3I:
			return {"_t": "v3i", "x": value.x, "y": value.y, "z": value.z}

		TYPE_RECT2:
			return {
				"_t": "r2",
				"x": value.position.x,
				"y": value.position.y,
				"w": value.size.x,
				"h": value.size.y,
			}

		TYPE_RECT2I:
			return {
				"_t": "r2i",
				"x": value.position.x,
				"y": value.position.y,
				"w": value.size.x,
				"h": value.size.y,
			}

		TYPE_COLOR:
			return {"_t": "col", "r": value.r, "g": value.g, "b": value.b, "a": value.a}

		TYPE_TRANSFORM2D:
			return {
				"_t": "t2d",
				"x": serialize(value.x),
				"y": serialize(value.y),
				"o": serialize(value.origin),
			}

		TYPE_NODE_PATH:
			return {"_t": "np", "v": str(value)}

		TYPE_ARRAY:
			var result: Array = []
			for element in value:
				result.append(serialize(element))
			return result

		TYPE_DICTIONARY:
			var result: Dictionary = {}
			for key in value:
				result[str(key)] = serialize(value[key])
			return result

		TYPE_PACKED_VECTOR2_ARRAY:
			var result: Array = []
			for vec in value:
				result.append(serialize(vec))
			return result

		TYPE_PACKED_FLOAT32_ARRAY:
			var result: Array = []
			for f in value:
				result.append(f)
			return result

		TYPE_PACKED_INT32_ARRAY:
			var result: Array = []
			for i in value:
				result.append(i)
			return result

		TYPE_PACKED_STRING_ARRAY:
			var result: Array = []
			for s in value:
				result.append(s)
			return result

		_:
			return {
				"_t": "_unknown",
				"_class": type_string(typeof(value)),
				"_str": str(value),
			}


static func deserialize(value: Variant) -> Variant:
	if value == null:
		return null

	if value is bool or value is int or value is float or value is String:
		return value

	if value is Array:
		var result: Array = []
		for element in value:
			result.append(deserialize(element))
		return result

	if value is Dictionary:
		if value.has("_t"):
			var tag: String = value["_t"]
			match tag:
				"v2":
					return Vector2(value["x"], value["y"])
				"v2i":
					return Vector2i(value["x"], value["y"])
				"v3":
					return Vector3(value["x"], value["y"], value["z"])
				"v3i":
					return Vector3i(value["x"], value["y"], value["z"])
				"r2":
					return Rect2(value["x"], value["y"], value["w"], value["h"])
				"r2i":
					return Rect2i(value["x"], value["y"], value["w"], value["h"])
				"col":
					return Color(value["r"], value["g"], value["b"], value["a"])
				"t2d":
					var x_axis: Vector2 = deserialize(value["x"])
					var y_axis: Vector2 = deserialize(value["y"])
					var origin: Vector2 = deserialize(value["o"])
					return Transform2D(x_axis, y_axis, origin)
				"np":
					return NodePath(value["v"])
				"_unknown":
					return value
				_:
					return value

		# Dictionary without _t: recursively deserialize values
		var result: Dictionary = {}
		for key in value:
			result[key] = deserialize(value[key])
		return result

	return value
