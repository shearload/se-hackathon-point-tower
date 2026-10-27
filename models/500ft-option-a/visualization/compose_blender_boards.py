"""Compose presentation boards from completed Blender renders.

Run only after structural_hero.png, studio_hero.png and outrigger_detail.png
have been rendered into ../tower_blender/. Source renders are not modified.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
RENDERS = Path(__file__).resolve().parent if Path(__file__).resolve().parent.name == 'visualization' else ROOT / 'tower_blender'
BG = '#f5f2ec'
INK = '#243a40'
MUTED = '#677678'
RULE = '#d9ddd7'
ORANGE = '#c57b39'
TEAL = '#347d7b'


def font(size, bold=False):
    name = 'arialbd.ttf' if bold else 'arial.ttf'
    return ImageFont.truetype(str(Path('C:/Windows/Fonts') / name), size)


def text(draw, xy, value, size=26, bold=False, color=INK):
    draw.text(xy, value, font=font(size, bold), fill=color)


def fit_image(board, path, box):
    """Fit the full render, retaining its original aspect ratio and contents."""
    with Image.open(path) as source:
        source = source.convert('RGBA')
        fitted = ImageOps.contain(source, (box[2] - box[0], box[3] - box[1]),
                                   Image.Resampling.LANCZOS)
        x = box[0] + (box[2] - box[0] - fitted.width) // 2
        y = box[1] + (box[3] - box[1] - fitted.height) // 2
        board.paste(fitted, (x, y), fitted)


def presentation_board():
    board = Image.new('RGB', (2400, 2020), BG)
    draw = ImageDraw.Draw(board)
    margin = 88
    text(draw, (margin, 55), 'POINT TOWER / OPTION A', 58, True)
    text(draw, (margin + 2, 132), 'CONCRETE CORE  /  STEEL OUTRIGGERS  /  FINITE FLOOR MEMBRANES',
         24, color=MUTED)
    draw.line((margin, 191, 2400 - margin, 191), fill=RULE, width=2)
    width, gap = 1084, 56
    headings = [('01', 'Structural', 'structural_hero.png', TEAL),
                ('02', 'Architectural studio', 'studio_hero.png', ORANGE)]
    for index, (number, label, filename, accent) in enumerate(headings):
        x = margin + index * (width + gap)
        text(draw, (x, 218), number, 23, True, accent)
        text(draw, (x + 49, 213), label, 32, True)
        draw.line((x, 264, x + 82, 264), fill=accent, width=4)
        fit_image(board, RENDERS / filename, (x, 290, x + width, 1684))
    draw.line((margin, 1736, 2400 - margin, 1736), fill=RULE, width=2)
    metric_columns = [
        ('500 ft', 'TOWER HEIGHT'),
        ('40', 'STORIES'),
        ('28', 'PERIMETER COLUMNS'),
        ('8', 'OUTRIGGER ARMS'),
    ]
    cell = (2400 - margin * 2) // 4
    for index, (value, label) in enumerate(metric_columns):
        x = margin + index * cell
        text(draw, (x, 1780), value, 48, True)
        text(draw, (x + 2, 1842), label, 21, color=MUTED)
        if index:
            draw.line((x - 32, 1790, x - 32, 1875), fill=RULE, width=2)
    draw.line((margin, 1910, 2400 - margin, 1910), fill=RULE, width=2)
    text(draw, (margin, 1944),
         'Conceptual visualization. Member sizes are placeholders pending structural design checks.',
         23, color=MUTED)
    target = RENDERS / 'presentation_board.png'
    board.save(target)
    return target


def detail_board():
    board = Image.new('RGB', (2400, 1870), BG)
    draw = ImageDraw.Draw(board)
    margin = 88
    text(draw, (margin, 52), 'POINT TOWER / OPTION A', 54, True)
    text(draw, (margin + 2, 124), 'PAIRED STEEL OUTRIGGERS AT THE CORE WALL ENDS', 25, color=MUTED)
    draw.line((margin, 178, 2400 - margin, 178), fill=RULE, width=2)
    # The image fills a full-width panel without changing its proportions.
    fit_image(board, RENDERS / 'outrigger_detail.png', (88, 212, 2312, 1396))
    draw.line((margin, 1432, 2400 - margin, 1432), fill=RULE, width=2)
    label_x = [88, 655, 1222, 1789]
    labels = [
        ('L26–L28', '325–350 ft', 'TWO-STORY TRUSS ZONE'),
        ('31.25 ft', '36 in walls', 'SQUARE CONCRETE CORE'),
        ('36 in / 18 in', 'Chords / diagonals', 'SOLID-SQUARE PLACEHOLDERS'),
        ('50 ksi', 'Steel yield strength', 'PAIRED TRUSS PLANES'),
    ]
    for index, (value, second, third) in enumerate(labels):
        x = label_x[index]
        color = TEAL if index == 1 else ORANGE if index in (0, 2) else INK
        text(draw, (x, 1472), value, 39, True, color)
        text(draw, (x, 1530), second, 25)
        text(draw, (x, 1573), third, 19, color=MUTED)
    draw.line((margin, 1630, 2400 - margin, 1630), fill=RULE, width=2)
    text(draw, (margin, 1663),
         'Eight arms in four wall-aligned planes. X diagonals share a central joint; the perimeter columns form the outer verticals.',
         24)
    text(draw, (margin, 1710),
         'Detail display: floors omitted; core and columns cropped to 310–365 ft. No structural geometry is displaced.',
         23, color=MUTED)
    text(draw, (margin, 1751),
         'Connections are conceptual; hardware, anchorage and fabrication cuts are not detailed. Sizes remain placeholders.',
         23, color=MUTED)
    target = RENDERS / 'detail_board.png'
    board.save(target)
    return target


def main():
    required = ['structural_hero.png', 'studio_hero.png', 'outrigger_detail.png']
    missing = [name for name in required if not (RENDERS / name).is_file()]
    if missing:
        raise FileNotFoundError('Wait for final Blender renders: ' + ', '.join(missing))
    for target in (presentation_board(), detail_board()):
        print(target)


if __name__ == '__main__':
    main()
