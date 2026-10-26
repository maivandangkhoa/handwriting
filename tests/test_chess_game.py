import chess

from src.chess_game import ChessGame

SQ = 88


def center(game, sq):
    x, y = game.square_origin(sq)
    return (x + game.square / 2, y + game.square / 2)


def move(game, src, dst):
    game.update(center(game, src), True)
    game.update(center(game, dst), True)
    game.update(center(game, dst), False)


def test_geometry_white_at_bottom():
    g = ChessGame(origin=(0, 0), square=SQ)
    assert g.square_at((44, 44)) == chess.A8
    assert g.square_at((44, 7 * SQ + 44)) == chess.A1
    assert g.square_at((7 * SQ + 44, 7 * SQ + 44)) == chess.H1
    assert g.square_at((-1, 10)) is None and g.square_at((8 * SQ, 10)) is None


def test_legal_move_by_pinch_drag_release():
    g = ChessGame(origin=(0, 0), square=SQ)
    move(g, chess.E2, chess.E4)
    assert g.board.piece_at(chess.E4).piece_type == chess.PAWN
    assert g.board.turn == chess.BLACK and g.last_move == chess.Move(chess.E2, chess.E4)


def test_pick_shows_legal_targets():
    g = ChessGame(origin=(0, 0), square=SQ)
    g.update(center(g, chess.G1), True)
    assert g.held == chess.G1 and g.targets == {chess.F3, chess.H3}


def test_illegal_drop_returns_piece():
    g = ChessGame(origin=(0, 0), square=SQ)
    move(g, chess.E2, chess.E5)
    assert g.board.piece_at(chess.E2) is not None and g.board.turn == chess.WHITE
    assert g.notice == "Illegal move." and g.held is None


def test_cannot_pick_opponent_piece_or_empty_square():
    g = ChessGame(origin=(0, 0), square=SQ)
    g.update(center(g, chess.E7), True)
    assert g.held is None
    g.update(center(g, chess.E7), False)
    g.update(center(g, chess.E4), True)
    assert g.held is None


def test_drop_outside_board_cancels():
    g = ChessGame(origin=(0, 0), square=SQ)
    g.update(center(g, chess.E2), True)
    g.update((5000, 5000), False)
    assert g.board.fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP")


def test_hand_lost_cancels_and_requires_re_pinch():
    g = ChessGame(origin=(0, 0), square=SQ)
    g.update(center(g, chess.E2), True)
    g.update(None, False)
    assert g.held is None and g.board.turn == chess.WHITE
    g.update(center(g, chess.D2), True)      # hand back while "still" pinching state change is a fresh pinch
    assert g.held == chess.D2


def test_lost_while_pinching_then_return_still_pinching_does_not_regrab():
    g = ChessGame(origin=(0, 0), square=SQ)
    g.update(center(g, chess.E2), True)
    g.update(None, True)
    g.update(center(g, chess.D2), True)
    assert g.held is None
    g.update(center(g, chess.D2), False)
    g.update(center(g, chess.D2), True)
    assert g.held == chess.D2


def test_checkmate_status_and_no_more_picks():
    g = ChessGame(origin=(0, 0), square=SQ)
    for a, b in [(chess.F2, chess.F3), (chess.E7, chess.E5), (chess.G2, chess.G4), (chess.D8, chess.H4)]:
        move(g, a, b)
    assert g.status == "Checkmate — Black wins"
    g.update(center(g, chess.E1), True)
    assert g.held is None


def test_promotion_defaults_to_queen():
    g = ChessGame(origin=(0, 0), square=SQ)
    g.board = chess.Board("8/P7/8/8/8/8/k7/4K3 w - - 0 1")
    move(g, chess.A7, chess.A8)
    assert g.board.piece_at(chess.A8).piece_type == chess.QUEEN


def test_new_game_resets():
    g = ChessGame(origin=(0, 0), square=SQ)
    move(g, chess.E2, chess.E4)
    g.new_game()
    assert g.board.fen() == chess.STARTING_FEN
