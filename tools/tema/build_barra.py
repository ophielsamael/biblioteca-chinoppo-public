"""Rebuild image_mediacenter.bin replacing image #260 (home icon bar) with a dark one.
Format: u32 count, count * <HHIIII (w, h, u1, u2, size, offset)>, then PNG blobs."""
import io, struct, sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
d = open(src, 'rb').read()
n = struct.unpack('<L', d[:4])[0]
hdr = [struct.unpack('<HHIIII', d[4+i*20:24+i*20]) for i in range(n)]
blobs = [d[o:o+s] for *_, s, o in hdr]

orig = Image.open(io.BytesIO(blobs[259]))
W, H = orig.size
bar = Image.new('RGBA', (W, H))
top, bot = (52, 58, 72, 190), (18, 20, 26, 220)        # slate -> near black (v2: a bit lighter)
for y in range(H):
    t = y / (H - 1)
    c = tuple(round(a + (b - a) * t) for a, b in zip(top, bot))
    bar.paste(c, (0, y, W, y + 1))
buf = io.BytesIO(); bar.save(buf, 'PNG', optimize=True); blobs[259] = buf.getvalue()
bar.save('bar_dark.png')

# Focus tiles (one colour per home icon): same shape/shadow, slate body with a thin light border.
from PIL import ImageChops, ImageFilter
TILES = (262, 265, 267, 268, 270, 272, 274)
for k in TILES:
    t = Image.open(io.BytesIO(blobs[k - 1])).convert('RGBA')
    body = t.getchannel('A').point(lambda a: 255 if a == 255 else 0)
    inner = body.filter(ImageFilter.MinFilter(7))
    x0, y0, x1, y1 = body.getbbox()
    grad = Image.new('RGBA', t.size)
    for y in range(t.height):
        f = min(max((y - y0) / max(y1 - y0 - 1, 1), 0), 1)
        grad.paste(tuple(round(a + (b - a) * f) for a, b in zip((104, 114, 132, 255), (62, 68, 82, 255))), (0, y, t.width, y + 1))
    t.paste(grad, (0, 0), body)
    t.paste((215, 220, 230, 255), (0, 0), ImageChops.subtract(body, inner))
    b2 = io.BytesIO(); t.save(b2, 'PNG', optimize=True); blobs[k - 1] = b2.getvalue()
    if k == 262: t.save('tile_262.png')

off = 4 + 20 * n
out = [struct.pack('<L', n)]
for (w, h, u1, u2, _, _), b in zip(hdr, blobs):
    out.append(struct.pack('<HHIIII', w, h, u1, u2, len(b), off)); off += len(b)
open(dst, 'wb').write(b''.join(out + blobs))

# self-check: re-read and compare every image except #260
r = open(dst, 'rb').read()
for i in range(n):
    w, h, u1, u2, s, o = struct.unpack('<HHIIII', r[4+i*20:24+i*20])
    assert (w, h, u1, u2) == hdr[i][:4]
    assert r[o:o+s] == blobs[i]
    if i != 259 and i + 1 not in TILES: assert r[o:o+s] == d[hdr[i][5]:hdr[i][5]+hdr[i][4]]
print('ok', n, len(r))
