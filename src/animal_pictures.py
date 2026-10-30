"""Animal outlines for the colouring app, as shapes on a 100 x 100 sheet. Later shapes lie on top of earlier ones.
A shape is ("ellipse", cx, cy, rx, ry) or ("poly", [(x, y), ...])."""

ANIMALS = {
    "Cat": [
        ("ellipse", 84, 70, 7, 22),                                    # tail
        ("ellipse", 50, 72, 28, 24),                                   # body
        ("poly", [(31, 26), (34, 6), (46, 20)]),                       # ears
        ("poly", [(69, 26), (66, 6), (54, 20)]),
        ("ellipse", 50, 38, 22, 19),                                   # head
        ("ellipse", 42, 36, 3.5, 3.5), ("ellipse", 58, 36, 3.5, 3.5),  # eyes
        ("ellipse", 50, 44, 2.5, 2.5),                                 # nose
    ],
    "Fish": [
        ("poly", [(73, 50), (96, 28), (96, 72)]),                      # tail
        ("poly", [(34, 34), (48, 12), (60, 34)]),                      # top fin
        ("ellipse", 45, 50, 32, 20),                                   # body
        ("ellipse", 54, 50, 5, 16),                                    # stripe
        ("ellipse", 30, 45, 4, 4),                                     # eye
    ],
    "Duck": [
        ("poly", [(22, 56), (6, 46), (20, 70)]),                       # tail
        ("ellipse", 50, 68, 32, 22),                                   # body
        ("ellipse", 46, 68, 15, 10),                                   # wing
        ("poly", [(79, 32), (96, 38), (79, 43)]),                      # beak
        ("ellipse", 66, 34, 16, 16),                                   # head
        ("ellipse", 70, 30, 2.8, 2.8),                                 # eye
    ],
    "Buffalo": [
        ("poly", [(88, 46), (95, 74), (89, 75), (83, 56)]),            # tail
        ("ellipse", 60, 50, 30, 21),                                   # body
        ("ellipse", 48, 34, 14, 10),                                   # shoulder hump
        ("poly", [(36, 66), (47, 66), (46, 94), (37, 94)]),            # legs
        ("poly", [(70, 66), (81, 66), (80, 94), (71, 94)]),
        ("poly", [(20, 36), (22, 22), (32, 12), (46, 8), (52, 10), (42, 16), (35, 24), (34, 38)]),   # horn, swept back
        ("ellipse", 24, 50, 15, 17),                                   # head
        ("poly", [(36, 42), (50, 46), (38, 52)]),                      # ear
        ("ellipse", 14, 66, 12, 8),                                    # muzzle
        ("ellipse", 21, 44, 2.8, 2.8),                                 # eye
        ("ellipse", 9, 66, 1.6, 1.6), ("ellipse", 16, 66, 1.6, 1.6),   # nostrils
    ],
}
