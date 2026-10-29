import chess

from src.chess_game import ChessGame

SQ = 88


def center(game, sq):
    x, y = game.square_origin(sq)
    return (x + game.square / 2, y + game.square / 2)


def tap(game, sq):
    """Finger lands on a square and lifts off again."""
    game.update(center(game, sq), True)
    game.update(center(game, sq), False)


def slide(game, src, dst):
    """Finger lands on `src`, slides along the surface and lifts off over `dst`."""
    game.update(center(game, src), True)
    game.update(center(game, dst), True)
    game.update(center(game, dst), False)


def new():
    return ChessGame(origin=(0, 0), square=SQ)


def test_geometry_white_at_bottom():
    g = new()
    assert g.square_at((44, 44)) == chess.A8
    assert g.square_at((44, 7 * SQ + 44)) == chess.A1
    assert g.square_at((7 * SQ + 44, 7 * SQ + 44)) == chess.H1
    assert g.square_at((-1, 10)) is None and g.square_at((8 * SQ, 10)) is None


def test_tap_piece_then_tap_destination_moves():
    g = new()
    tap(g, chess.E2)
    assert g.held == chess.E2 and g.targets == {chess.E3, chess.E4}
    tap(g, chess.E4)
    assert g.board.piece_at(chess.E4).piece_type == chess.PAWN
    assert g.board.turn == chess.BLACK and g.last_move == chess.Move(chess.E2, chess.E4) and g.held is None


def test_slide_from_piece_to_destination_moves():
    g = new()
    slide(g, chess.G1, chess.F3)
    assert g.board.piece_at(chess.F3).piece_type == chess.KNIGHT and g.board.turn == chess.BLACK


def test_selection_survives_the_hand_leaving():
    g = new()
    tap(g, chess.E2)
    g.update(None, False)
    assert g.held == chess.E2
    tap(g, chess.E3)
    assert g.board.piece_at(chess.E3) is not None


def test_touching_the_selected_piece_again_deselects():
    g = new()
    tap(g, chess.E2)
    tap(g, chess.E2)
    assert g.held is None and g.targets == set()


def test_touching_another_own_piece_changes_selection():
    g = new()
    tap(g, chess.E2)
    tap(g, chess.G1)
    assert g.held == chess.G1 and g.board.turn == chess.WHITE


def test_illegal_destination_deselects_with_notice():
    g = new()
    tap(g, chess.E2)
    tap(g, chess.E5)
    assert g.held is None and g.notice == "Illegal move." and g.board.turn == chess.WHITE


def test_slide_to_illegal_square_deselects_with_notice():
    g = new()
    slide(g, chess.E2, chess.E5)
    assert g.held is None and g.notice == "Illegal move." and g.board.piece_at(chess.E2) is not None


def test_cannot_pick_opponent_piece_or_empty_square():
    g = new()
    tap(g, chess.E7)
    assert g.held is None and g.notice
    tap(g, chess.E4)
    assert g.held is None


def test_touch_outside_the_board_is_ignored_and_keeps_nothing_selected():
    g = new()
    g.update((5000, 5000), True)
    g.update((5000, 5000), False)
    assert g.held is None and g.board.fen() == chess.STARTING_FEN


def test_a_held_touch_acts_once():
    g = new()
    g.update(center(g, chess.E2), True)
    g.update(center(g, chess.E2), True)
    g.update(center(g, chess.E2), True)
    assert g.held == chess.E2     # not toggled off by the repeated frames


def test_checkmate_status_and_no_more_picks():
    g = new()
    for a, b in [(chess.F2, chess.F3), (chess.E7, chess.E5), (chess.G2, chess.G4), (chess.D8, chess.H4)]:
        board_move(g, a, b)
    assert g.status == "Checkmate — Black wins"
    tap(g, chess.E1)
    assert g.held is None


def board_move(g, a, b):
    g.board.push(chess.Move(a, b))


def test_promotion_defaults_to_queen():
    g = new()
    g.board = chess.Board("8/P7/8/8/8/8/k7/4K3 w - - 0 1")
    tap(g, chess.A7)
    tap(g, chess.A8)
    assert g.board.piece_at(chess.A8).piece_type == chess.QUEEN


def test_revision_changes_when_the_board_changes():
    g = new()
    r = g.revision
    tap(g, chess.E2)
    assert g.revision == r        # selecting alone does not change the projected squares' contents
    tap(g, chess.E4)
    assert g.revision == r + 1
    g.new_game()
    assert g.revision == r + 2


def test_new_game_resets():
    g = new()
    slide(g, chess.E2, chess.E4)
    g.new_game()
    assert g.board.fen() == chess.STARTING_FEN and g.held is None
