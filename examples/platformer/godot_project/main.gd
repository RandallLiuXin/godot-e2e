extends Node2D

var score: int = 0
var player_alive: bool = true

func _process(delta):
    var player = $Player
    if Input.is_action_pressed("ui_right"):
        player.position.x += 200.0 * delta
    if Input.is_action_pressed("ui_left"):
        player.position.x -= 200.0 * delta
    if Input.is_action_just_pressed("ui_accept"):
        score += 1
        $HUD/ScoreLabel.text = "Score: " + str(score)

func get_score() -> int:
    return score
