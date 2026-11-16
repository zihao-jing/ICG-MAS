"""A single middle-stage replacement must preserve every other agent's board units."""

from scripts.run_single_middle_swap import replacement_board


def test_only_selected_agent_units_change():
    record = {"board_units": [
        {"unit_id": "a0u0", "agent_id": 0, "text": "first original"},
        {"unit_id": "a0u1", "agent_id": 0, "text": "second original"},
        {"unit_id": "a1u0", "agent_id": 1, "text": "other agent"},
    ]}
    board = replacement_board(record, 0, ["Gemini unit"])
    assert [unit["text"] for unit in board if unit["agent_id"] == 0] == ["Gemini unit"]
    assert [unit for unit in board if unit["agent_id"] == 1] == [record["board_units"][2]]
    assert record["board_units"][0]["text"] == "first original"
