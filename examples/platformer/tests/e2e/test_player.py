"""Example E2E tests for the platformer."""


def test_player_exists(game):
    assert game.node_exists("/root/Main/Player")


def test_player_in_group(game):
    players = game.find_by_group("player")
    assert len(players) == 1


def test_player_moves_right(game):
    initial_x = game.get_property("/root/Main/Player", "position:x")
    game.input_action("ui_right", True)
    game.wait_physics_frames(10)
    game.input_action("ui_right", False)
    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x


def test_score_increments(game):
    assert game.get_property("/root/Main", "score") == 0
    game.press_action("ui_accept")
    score = game.get_property("/root/Main", "score")
    assert score == 1


def test_scene_reload_resets_score(game):
    game.press_action("ui_accept")
    game.press_action("ui_accept")
    assert game.get_property("/root/Main", "score") == 2
    game.reload_scene()
    game.wait_for_node("/root/Main", timeout=5.0)
    assert game.get_property("/root/Main", "score") == 0
