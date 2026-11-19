"""Pictures of array selections as PNG, with the standard library only.

A one-dimensional selection, or a two-dimensional one with a short axis, is
drawn as lines over the coordinates of the long axis; a two-dimensional one
as a map with a color bar. Ticks follow the coordinates read_array returns,
so the picture carries units and positions. Complex values are drawn as
magnitude, real or imaginary part, phase or power. A map keeps square cells
when both axes are uniform lengths in the same unit. Viridis is used for
one-signed values, a blue-white-red scale centred on zero for signed ones
and a hue circle for phase; cells without a finite value are gray.
"""
import math
import struct
import zlib

# 5 x 8 glyphs of printable ASCII from the space, each 40 bits read row by row from the top left;
# the last row holds descenders.
FONT = ('00000000002108420080529400000052beafa94023e8e2f880c644444c6064a88ac9a0210800000011108410404104211100012aea9000'
        '0109f2100000000030880001f000000000003180004444400074675cc5c023084211c074422223e0f88820c5c011952f8840fc3c10c5c0'
        '3221e8c5c0f8444421007462e8c5c07462f08980031806300003180611001111041040003e0f8000410411110074422200807442dad5c0'
        '7463f8c620f463e8c7c074610845c0e4a318cb80fc21e843e0fc21e84200746178c5e08c63f8c62071084211c038842149808ca98a4a20'
        '84210843e08eeb58c6208c7359c620746318c5c0f463e8420074631ac9a0f463ea4a207c20e087c0f9084210808c6318c5c08c6318a880'
        '8c635ad5408c544546208c62a21080f8444443e072108421c0041041040070842109c022a200000000000003e04104000000001c17c5e0'
        '842d98c7c0001d0845c0085b38c5e0001d1fc1c03251c42100001f18bc2e842d98c62020184211c0100c210a4c84254c524061084211c0'
        '00355ac620002d98c620001d18c5c0003d18fa10001f18bc21002d984200001d0707c042388424c0002318cda0002318a88000231ad540'
        '0022a22a20002318bc2e003e2223e01108821040210842108041082211000011510000')


def glyph(character):
    code = ord(character)
    code = code if 32 <= code < 127 else ord('?')
    return int(FONT[(code - 32) * 10:(code - 31) * 10], 16)


VIRIDIS = [(68, 1, 84), (71, 45, 123), (59, 82, 139), (44, 114, 142), (33, 144, 140), (39, 173, 129), (93, 200, 99),
           (170, 220, 50), (253, 231, 37)]
DIVERGING = [(5, 48, 97), (33, 102, 172), (67, 147, 195), (146, 197, 222), (209, 229, 240), (247, 247, 247),
             (253, 219, 199), (244, 165, 130), (214, 96, 77), (178, 24, 43), (103, 0, 31)]
LINES = [(78, 121, 167), (242, 142, 43), (225, 87, 89), (118, 183, 178), (89, 161, 79), (237, 201, 72), (176, 122, 161),
         (255, 157, 167), (156, 117, 95), (186, 176, 172)]
INK, GRID, MISSING, WHITE = (40, 40, 40), (228, 228, 228), (200, 200, 200), (255, 255, 255)
FOLD = {'µ': 'u', 'μ': 'u', 'Å': 'A', '°': 'deg', '²': '^2', '³': '^3', '⁻': '^-', '¹': '1', '·': '*', '–': '-', '—': '-', '×': 'x',
        'λ': 'lambda', 'π': 'pi', 'ω': 'omega', 'Ω': 'Omega'}


def ascii_text(text):
    return ''.join(FOLD.get(c, c) for c in str(text))


def scale_color(scale, t):
    """A color of a scale at position t in [0, 1]."""
    if not math.isfinite(t):
        return MISSING
    t = min(1.0, max(0.0, t)) * (len(scale) - 1)
    k = min(int(t), len(scale) - 2)
    f = t - k
    return tuple(int(round(a + (b - a) * f)) for a, b in zip(scale[k], scale[k + 1]))


def hue(t):
    """A cyclic color for t in [0, 1): hue circle at full saturation and moderate value."""
    if not math.isfinite(t):
        return MISSING
    h = (t % 1.0) * 6
    k, f = int(h), h - int(h)
    v, p = 0.9, 0.15
    q, r = v - (v - p) * f, p + (v - p) * f
    rgb = [(v, r, p), (q, v, p), (p, v, r), (p, q, v), (r, p, v), (v, p, q)][k % 6]
    return tuple(int(round(255 * c)) for c in rgb)


class Canvas:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.pixels = bytearray(b'\xff' * (width * height * 3))

    def point(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.pixels[i:i + 3] = bytes(color)

    def rectangle(self, x0, y0, x1, y1, color):
        """Fill [x0, x1) x [y0, y1)."""
        x0, x1 = max(0, min(x0, x1)), min(self.width, max(x0, x1))
        row = bytes(color) * max(0, x1 - x0)
        for y in range(max(0, min(y0, y1)), min(self.height, max(y0, y1))):
            i = (y * self.width + x0) * 3
            self.pixels[i:i + len(row)] = row

    def line(self, x0, y0, x1, y1, color, width=1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error, half = dx + dy, width // 2
        while True:
            self.rectangle(x0 - half, y0 - half, x0 - half + width, y0 - half + width, color)
            if x0 == x1 and y0 == y1:
                return
            double = 2 * error
            if double >= dy:
                error += dy
                x0 += sx
            if double <= dx:
                error += dx
                y0 += sy

    def text(self, x, y, text, color=INK, size=2, anchor='left', vertical=False):
        """Draw text with its top-left (or centre, or right end) at x, y; vertical text reads upward."""
        text = ascii_text(text)
        length = len(text) * 6 * size - size
        shift = {'left': 0, 'center': length // 2, 'right': length}[anchor]
        for n, character in enumerate(text):
            bits = glyph(character)
            for row in range(8):
                for column in range(5):
                    if bits >> (39 - row * 5 - column) & 1:
                        along, across = n * 6 * size + column * size - shift, row * size
                        if vertical:
                            self.rectangle(x + across, y - along - size, x + across + size, y - along, color)
                        else:
                            self.rectangle(x + along, y + across, x + along + size, y + across + size, color)

    def png(self):
        rows = b''.join(b'\x00' + bytes(self.pixels[y * self.width * 3:(y + 1) * self.width * 3]) for y in range(self.height))

        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', self.width, self.height, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(rows, 6)) + chunk(b'IEND', b''))


def ticks(low, high, count=6):
    """Round tick values covering [low, high]."""
    if not (math.isfinite(low) and math.isfinite(high)) or high <= low:
        return [low] if math.isfinite(low) else []
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if (high - low) / (m * magnitude) <= count)
    first = math.ceil(low / step - 1e-9) * step
    values, k = [], 0
    while first + k * step <= high + step * 1e-9:
        values.append(first + k * step)
        k += 1
    return values


def label(value, step=None):
    """A short number for a tick or a color bar; step sets the decimals of evenly spaced ticks."""
    if value == 0:
        return '0'
    if 1e-3 <= abs(value) < 1e5:
        if step is not None:
            return f'{value:.{min(6, max(0, -math.floor(math.log10(step) + 1e-9)))}f}'
        return str(int(value)) if float(value).is_integer() else f'{value:.5g}'
    mantissa, exponent = f'{value:.2e}'.split('e')
    return mantissa.rstrip('0').rstrip('.') + 'e' + str(int(exponent))


def finite(values):
    return [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return {'nan': math.nan, 'inf': math.inf, '-inf': -math.inf}.get(value, math.nan)


def flatten(nested):
    if isinstance(nested, list):
        return [x for item in nested for x in flatten(item)]
    return [nested]


def part_values(selection, part):
    """The selected values as numbers, taking part of complex ones: abs, real, imag, phase or power."""
    if 'real' in selection:
        real = [number(v) for v in flatten(selection['real'])]
        imag = [number(v) for v in flatten(selection['imag'])]
        if part == 'real':
            return real, 'real part of '
        if part == 'imag':
            return imag, 'imaginary part of '
        if part == 'phase':
            return [math.atan2(b, a) for a, b in zip(real, imag)], 'phase (rad) of '
        if part == 'power':
            return [a * a + b * b for a, b in zip(real, imag)], '|.|^2 of '
        return [math.hypot(a, b) for a, b in zip(real, imag)], '|.| of '
    values = [number(v) for v in flatten(selection['values'])]
    if part == 'abs':
        return [abs(v) for v in values], '|.| of '
    if part == 'power':
        return [v * v for v in values], '(.)^2 of '
    if part in ('imag', 'phase'):
        raise ValueError(part + ' applies to complex arrays')
    return values, ''


def axis_title(axis):
    unit = axis.get('unit')
    return axis['name'] + (f' [{unit}]' if unit else '')


def coordinates(axes, k, length):
    """Numeric coordinates of kept axis k, or None for labels or a missing description."""
    if axes and k < len(axes):
        values = axes[k].get('values')
        if values is not None and len(values) == length and all(isinstance(v, (int, float)) for v in values):
            return [float(v) for v in values]
    return None


def heading(selection, prefix):
    description = selection.get('description', {})
    quantity = description.get('quantity') or selection.get('member') or 'values'
    unit = description.get('unit')
    title = prefix + quantity + (f' [{unit}]' if unit and unit != '1' else '')
    fixed = ', '.join(f"{item['name']}={label(item['value']) if isinstance(item['value'], (int, float)) else item['value']}"
                      for item in selection.get('at', []))
    return title, fixed


def picture(selection, kind='auto', part=None, scale='linear', width=880, height=560):
    """PNG bytes and a summary of a read_array selection.

    kind is auto, line or map; part takes abs, real, imag, phase or power of
    complex values; scale log draws log10 of positive values.
    """
    shape = selection['result_shape']
    complex_values = 'real' in selection
    part = part or ('abs' if complex_values else 'real')
    values, prefix = part_values(selection, part)
    if len(shape) == 0 or len(shape) > 2 or not values:
        raise ValueError(f'A picture needs a one- or two-dimensional selection; this one has shape {shape}. Fix axes with index')
    if kind not in ('auto', 'line', 'map') or scale not in ('linear', 'log'):
        raise ValueError('kind is auto, line or map; scale is linear or log')
    axes = selection.get('axes') or []
    if kind == 'auto':
        kind = 'line' if len(shape) == 1 or min(shape) <= 8 else 'map'
    if kind == 'map' and len(shape) != 2:
        raise ValueError('A map needs a two-dimensional selection')
    summary = summarize(values, shape, axes)
    if scale == 'log':
        if part == 'phase':
            raise ValueError('A phase is drawn on a linear scale')
        values = [math.log10(v) if v > 0 else math.nan for v in values]
    canvas = Canvas(width, height)
    title, fixed = heading(selection, prefix)
    canvas.text(width // 2, 10, title[:70], size=2, anchor='center')
    if fixed:
        canvas.text(width // 2, 30, fixed[:100], size=1, anchor='center', color=(90, 90, 90))
    (draw_lines if kind == 'line' else draw_map)(canvas, values, shape, axes, part, scale == 'log')
    return canvas.png(), {**summary, 'drawn': {'kind': kind, 'part': part, 'scale': scale}}


def tick_labels(low, high, logarithmic, count=6):
    """Positions and texts of ticks; on a log scale positions are log10 of the value."""
    if logarithmic and high - low >= 1:
        step = max(1, math.ceil((high - low) / count))
        first = math.ceil(low)
        return [(v, f'1e{v}' if v < -3 or v > 4 else label(10.0 ** v)) for v in range(first, math.floor(high) + 1, step)]
    values = ticks(low, high, count)
    step = values[1] - values[0] if len(values) > 1 else None
    return [(v, label(10.0 ** v, None) if logarithmic else label(v, step)) for v in values]


def summarize(values, shape, axes):
    good = [(v, n) for n, v in enumerate(values) if math.isfinite(v)]
    summary = {'shape': shape, 'finite': len(good), 'missing': len(values) - len(good)}
    if good:
        low, high = min(good), max(good)
        summary.update(min=low[0], max=high[0], mean=sum(v for v, _ in good) / len(good))

        def where(n):
            place, index = {}, []
            for size in reversed(shape):
                index.append(n % size)
                n //= size
            for k, i in enumerate(reversed(index)):
                axis = axes[k] if k < len(axes) else {'name': f'axis {k}'}
                listed = axis.get('values', axis.get('labels'))
                place[axis['name']] = listed[i] if listed is not None and i < len(listed) else i
            return place
        summary.update(at_min=where(low[1]), at_max=where(high[1]))
    return summary


FRAME = {'left': 110, 'right': 30, 'top': 56, 'bottom': 70}


def draw_lines(canvas, values, shape, axes, part, logarithmic=False):
    legend = None
    if len(shape) == 1:
        series, along, names = [values], 0, [None]
    else:
        along = 1 if shape[1] >= shape[0] else 0
        count, length = shape[1 - along], shape[along]
        series = [[values[i * shape[1] + j] if along == 1 else values[j * shape[1] + i] for j in range(length)] for i in range(count)]
        other = axes[1 - along] if len(axes) > 1 - along else {'name': 'index'}
        listed = other.get('values', other.get('labels')) or list(range(count))
        names = [label(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v) for v in listed]
        legend = axis_title(other)
    length = shape[along]
    x = coordinates(axes, along, length) or [float(i) for i in range(length)]
    xname = axis_title(axes[along]) if len(axes) > along else 'index'
    left, right = FRAME['left'], canvas.width - FRAME['right']
    top, bottom = FRAME['top'], canvas.height - FRAME['bottom']
    data = finite([v for line in series for v in line])
    if not data:
        canvas.text((left + right) // 2, (top + bottom) // 2, 'no finite values', anchor='center')
        return
    low, high = min(data), max(data)
    if high == low:
        low, high = low - (abs(low) or 1) * 0.1, high + (abs(high) or 1) * 0.1
    pad = (high - low) * 0.05
    low, high = low - pad, high + pad
    xlow, xhigh = min(x), max(x)
    if xhigh == xlow:
        xlow, xhigh = xlow - 1, xhigh + 1
    px = lambda v: int(round(left + (v - xlow) / (xhigh - xlow) * (right - left)))  # noqa: E731
    py = lambda v: int(round(bottom - (v - low) / (high - low) * (bottom - top)))  # noqa: E731
    xt = ticks(xlow, xhigh, 7)
    xstep = xt[1] - xt[0] if len(xt) > 1 else None
    for v, text in tick_labels(low, high, logarithmic):
        canvas.line(left, py(v), right, py(v), GRID)
        canvas.text(left - 8, py(v) - 7, text, anchor='right')
    for v in xt:
        canvas.line(px(v), top, px(v), bottom, GRID)
        canvas.text(px(v), bottom + 8, label(v, xstep), anchor='center')
    canvas.line(left, top, left, bottom, INK)
    canvas.line(left, bottom, right, bottom, INK)
    canvas.text((left + right) // 2, bottom + 34, xname[:60], anchor='center')
    for n, line in enumerate(series):
        color = LINES[n % len(LINES)]
        previous = None
        for xv, yv in zip(x, line):
            if not math.isfinite(yv):
                previous = None
                continue
            here = (px(xv), py(yv))
            if previous:
                canvas.line(previous[0], previous[1], here[0], here[1], color, width=2)
            if length <= 40:
                canvas.rectangle(here[0] - 3, here[1] - 3, here[0] + 4, here[1] + 4, color)
            previous = here
    if legend is not None:
        canvas.text(right - 190, top + 6, legend[:30], size=1, color=(90, 90, 90))
        for n, name in enumerate(names[:10]):
            y = top + 20 + n * 18
            canvas.rectangle(right - 190, y + 5, right - 170, y + 9, LINES[n % len(LINES)])
            canvas.text(right - 164, y, name[:13], size=2)


def draw_map(canvas, values, shape, axes, part, logarithmic=False):
    rows, columns = shape
    y = coordinates(axes, 0, rows)
    x = coordinates(axes, 1, columns)
    data = finite(values)
    left, top = FRAME['left'], FRAME['top']
    right, bottom = canvas.width - FRAME['right'] - 110, canvas.height - FRAME['bottom']
    width, height = right - left, bottom - top
    # Square cells for two lengths in one unit, unless that would squeeze the map into a strip.
    same = x and y and len(axes) > 1 and axes[0].get('unit') and axes[0].get('unit') == axes[1].get('unit') and rows > 1 and columns > 1
    if same:
        spanx, spany = abs(x[-1] - x[0]) * columns / (columns - 1), abs(y[-1] - y[0]) * rows / (rows - 1)
        if spanx > 0 and spany > 0:
            scale = min(width / spanx, height / spany)
            if spanx * scale >= width / 4 and spany * scale >= height / 4:
                width, height = max(1, int(spanx * scale)), max(1, int(spany * scale))
                right, bottom = left + width, top + height
    if part == 'phase':
        color = lambda v: hue((v + math.pi) / (2 * math.pi))  # noqa: E731
        low, high = -math.pi, math.pi
    elif data and min(data) < 0 < max(data) and not logarithmic:
        reach = max(abs(min(data)), abs(max(data)))
        low, high = -reach, reach
        color = lambda v: scale_color(DIVERGING, (v + reach) / (2 * reach))  # noqa: E731
    else:
        low, high = (min(data), max(data)) if data else (0.0, 1.0)
        if high == low:
            high = low + (abs(low) or 1.0)
        color = lambda v: scale_color(VIRIDIS, (v - low) / (high - low))  # noqa: E731
    colors = [color(v) for v in values]
    for py in range(height):
        row = rows - 1 - min(rows - 1, py * rows // height)  # the first index increases upward
        line = bytearray()
        for px in range(width):
            line += bytes(colors[row * columns + min(columns - 1, px * columns // width)])
        i = ((top + py) * canvas.width + left) * 3
        canvas.pixels[i:i + len(line)] = line
    canvas.line(left - 1, top - 1, left - 1, bottom, INK)
    canvas.line(left - 1, bottom, right, bottom, INK)

    def axis_ticks(coordinate, count, along_x):
        if coordinate is None:
            listed = axes[1 if along_x else 0].get('labels') if len(axes) > (1 if along_x else 0) else None
            positions = range(count) if count <= 12 else range(0, count, max(1, count // 6))
            return [((p + 0.5) / count, str(listed[p]) if listed else str(p)) for p in positions]
        first, last = coordinate[0], coordinate[-1]
        if first == last:
            return [(0.5, label(first))]
        values = ticks(min(first, last), max(first, last), 6)
        step = values[1] - values[0] if len(values) > 1 else None
        return [(((v - first) / (last - first) * (count - 1) + 0.5) / count, label(v, step)) for v in values]
    for fraction, text in axis_ticks(x, columns, True):
        p = int(left + fraction * width)
        canvas.line(p, bottom, p, bottom + 5, INK)
        canvas.text(p, bottom + 10, text[:10], anchor='center')
    for fraction, text in axis_ticks(y, rows, False):
        p = int(bottom - fraction * height)
        canvas.line(left - 6, p, left - 1, p, INK)
        canvas.text(left - 10, p - 7, text[:9], anchor='right')
    if len(axes) > 1:
        canvas.text((left + right) // 2, bottom + 36, axis_title(axes[1])[:50], anchor='center')
    if axes:
        canvas.text(16, (top + bottom) // 2 + len(axis_title(axes[0])[:30]) * 6, axis_title(axes[0])[:30], vertical=True)
    # Color bar beside the map.
    bar_left, bar_top, bar_bottom = right + 24, top, bottom
    for py in range(bar_top, bar_bottom):
        v = high - (py - bar_top) / max(1, bar_bottom - bar_top - 1) * (high - low)
        canvas.rectangle(bar_left, py, bar_left + 18, py + 1, color(v))
    for v, text in tick_labels(low, high, logarithmic):
        p = int(bar_top + (high - v) / (high - low) * (bar_bottom - bar_top - 1))
        canvas.line(bar_left + 18, p, bar_left + 22, p, INK)
        canvas.text(bar_left + 26, p - 7, text[:8], size=1 if len(text) > 7 else 2)
