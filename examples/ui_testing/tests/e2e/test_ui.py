"""UI testing example: buttons, labels, and scene navigation."""


def test_initial_ui_state(game):
    """Verify the menu scene loads with correct initial state."""
    title = game.get_property("/root/Menu/VBox/TitleLabel", "text")
    assert title == "UI Testing Demo"

    status = game.get_property("/root/Menu/VBox/StatusLabel", "text")
    assert status == "Not clicked yet"


def test_button_click_updates_label(game):
    """Click a button and verify the label updates."""
    game.click_node("/root/Menu/VBox/ClickButton")
    game.wait_process_frames(2)

    status = game.get_property("/root/Menu/VBox/StatusLabel", "text")
    assert status == "Clicked 1 times"

    game.click_node("/root/Menu/VBox/ClickButton")
    game.wait_process_frames(2)

    status = game.get_property("/root/Menu/VBox/StatusLabel", "text")
    assert status == "Clicked 2 times"


def test_navigate_to_detail_page(game):
    """Click navigate button and verify scene changes."""
    game.click_node("/root/Menu/VBox/NavigateButton")
    game.wait_for_node("/root/Detail", timeout=5.0)

    label = game.get_property("/root/Detail/VBox/DetailLabel", "text")
    assert label == "Detail Page"


def test_navigate_back_to_menu(game):
    """Navigate to detail page and back to menu."""
    game.click_node("/root/Menu/VBox/NavigateButton")
    game.wait_for_node("/root/Detail", timeout=5.0)

    game.click_node("/root/Detail/VBox/BackButton")
    game.wait_for_node("/root/Menu", timeout=5.0)

    title = game.get_property("/root/Menu/VBox/TitleLabel", "text")
    assert title == "UI Testing Demo"


def test_scene_change_api(game):
    """Use the change_scene API directly."""
    game.change_scene("res://detail.tscn")
    game.wait_for_node("/root/Detail", timeout=5.0)

    assert game.node_exists("/root/Detail/VBox/BackButton")
