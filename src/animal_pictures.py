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
    "Rabbit": [
        ("ellipse", 36, 20, 8, 19), ("ellipse", 64, 20, 8, 19),        # ears
        ("ellipse", 36, 22, 3.5, 12), ("ellipse", 64, 22, 3.5, 12),    # inner ears
        ("ellipse", 50, 78, 24, 19),                                   # body
        ("ellipse", 35, 94, 10, 5), ("ellipse", 65, 94, 10, 5),        # feet
        ("ellipse", 50, 52, 25, 21),                                   # head
        ("ellipse", 41, 48, 3.5, 3.5), ("ellipse", 59, 48, 3.5, 3.5),  # eyes
        ("ellipse", 36, 58, 5, 3.5), ("ellipse", 64, 58, 5, 3.5),      # cheeks
        ("ellipse", 50, 56, 3, 2.4),                                   # nose
    ],
    "Pig": [
        ("ellipse", 88, 62, 4, 4),                                     # tail
        ("ellipse", 50, 68, 36, 22),                                   # body
        ("poly", [(26, 80), (38, 80), (38, 95), (26, 95)]),            # legs
        ("poly", [(62, 80), (74, 80), (74, 95), (62, 95)]),
        ("poly", [(26, 30), (22, 8), (42, 22)]),                       # ears
        ("poly", [(74, 30), (78, 8), (58, 22)]),
        ("ellipse", 50, 40, 26, 22),                                   # head
        ("ellipse", 50, 49, 11, 8),                                    # snout
        ("ellipse", 46, 49, 1.8, 2.4), ("ellipse", 54, 49, 1.8, 2.4),  # nostrils
        ("ellipse", 40, 34, 3, 3), ("ellipse", 60, 34, 3, 3),          # eyes
    ],
    "Elephant": [
        ("ellipse", 90, 52, 3, 8),                                     # tail
        ("ellipse", 58, 56, 31, 25),                                   # body
        ("poly", [(40, 74), (54, 74), (53, 95), (41, 95)]),            # legs
        ("poly", [(66, 74), (80, 74), (79, 95), (67, 95)]),
        ("ellipse", 30, 44, 19, 19),                                   # head
        ("poly", [(18, 52), (9, 64), (9, 88), (17, 88), (18, 70), (26, 60)]),   # trunk
        ("ellipse", 42, 46, 12, 17),                                   # ear
        ("ellipse", 26, 39, 2.8, 2.8),                                 # eye
        ("poly", [(14, 58), (6, 62), (13, 66)]),                       # tusk
    ],
    "Bear": [
        ("ellipse", 27, 24, 9, 9), ("ellipse", 73, 24, 9, 9),          # ears
        ("ellipse", 27, 25, 4.5, 4.5), ("ellipse", 73, 25, 4.5, 4.5),
        ("ellipse", 50, 78, 27, 20),                                   # body
        ("ellipse", 50, 82, 15, 13),                                   # belly
        ("ellipse", 30, 94, 9, 5), ("ellipse", 70, 94, 9, 5),          # feet
        ("ellipse", 50, 46, 27, 24),                                   # head
        ("ellipse", 50, 56, 12, 9),                                    # muzzle
        ("ellipse", 50, 52, 4, 3),                                     # nose
        ("ellipse", 40, 40, 3.2, 3.2), ("ellipse", 60, 40, 3.2, 3.2),  # eyes
    ],
    "Owl": [
        ("poly", [(26, 30), (24, 8), (42, 22)]),                       # ear tufts
        ("poly", [(74, 30), (76, 8), (58, 22)]),
        ("ellipse", 50, 58, 29, 35),                                   # body
        ("ellipse", 20, 64, 8, 21), ("ellipse", 80, 64, 8, 21),        # wings
        ("ellipse", 50, 72, 18, 20),                                   # belly
        ("poly", [(38, 92), (30, 97), (46, 97)]),                      # feet
        ("poly", [(62, 92), (54, 97), (70, 97)]),
        ("ellipse", 38, 42, 11, 11), ("ellipse", 62, 42, 11, 11),      # eye discs
        ("ellipse", 38, 42, 4.5, 4.5), ("ellipse", 62, 42, 4.5, 4.5),  # pupils
        ("poly", [(45, 50), (55, 50), (50, 60)]),                      # beak
    ],
    "Turtle": [
        ("poly", [(14, 66), (4, 72), (16, 72)]),                       # tail
        ("ellipse", 30, 78, 8, 8), ("ellipse", 68, 78, 8, 8),          # legs
        ("ellipse", 87, 52, 12, 10),                                   # head
        ("ellipse", 46, 56, 36, 25),                                   # shell
        ("ellipse", 46, 50, 11, 8),                                    # shell pattern
        ("ellipse", 28, 58, 7, 7), ("ellipse", 64, 58, 7, 7),
        ("ellipse", 91, 49, 2.6, 2.6),                                 # eye
    ],
    "Penguin": [
        ("ellipse", 50, 54, 28, 39),                                   # body
        ("ellipse", 50, 62, 19, 28),                                   # belly
        ("ellipse", 20, 58, 7, 19), ("ellipse", 80, 58, 7, 19),        # flippers
        ("ellipse", 36, 94, 11, 4.5), ("ellipse", 64, 94, 11, 4.5),    # feet
        ("ellipse", 50, 34, 19, 17),                                   # face
        ("ellipse", 42, 32, 3.2, 3.2), ("ellipse", 58, 32, 3.2, 3.2),  # eyes
        ("poly", [(43, 40), (57, 40), (50, 50)]),                      # beak
    ],
}
