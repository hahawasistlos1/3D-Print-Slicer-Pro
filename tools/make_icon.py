"""Render the split-cube brand mark for the window header and Windows shell."""
from pathlib import Path
import struct
import zlib

import numpy as np


SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render(size):
    samples = 4
    resolution = samples * size
    x = (np.arange(resolution)[None, :] + .5) * 64 / resolution
    y = x.T
    canvas = np.zeros((resolution, resolution, 4), dtype=np.uint8)

    def polygon(points, top, bottom):
        mask = np.ones((resolution, resolution), dtype=bool)
        for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
            mask &= (bx - ax) * (y - ay) - (by - ay) * (x - ax) >= 0
        ymin = min(point[1] for point in points)
        ymax = max(point[1] for point in points)
        slope = np.clip((y - ymin) / (ymax - ymin), 0, 1)
        colors = np.rint(np.asarray(top) + slope * (np.asarray(bottom) - top))
        canvas[mask, :3] = np.broadcast_to(colors[:, None, :], canvas[:, :, :3].shape)[mask]
        canvas[mask, 3] = 255

    def line(points, color, width):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx - ax, by - ay
            t = np.clip(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
            mask = (x - ax - t * dx)**2 + (y - ay - t * dy)**2 <= (width / 2)**2
            canvas[mask] = (*color, 255)

    edge = max(1.8, 44 / size)
    # Lower half of the block. The dark upper face separates the two pieces.
    polygon([(6, 28), (32, 14), (58, 28), (32, 42)], (23, 84, 109), (17, 69, 93))
    polygon([(6, 28), (32, 42), (32, 59), (6, 45)], (26, 160, 204), (12, 89, 139))
    polygon([(32, 42), (58, 28), (58, 45), (32, 59)], (13, 110, 156), (13, 55, 97))
    line([(6, 28), (6, 45), (32, 59), (58, 45), (58, 28)], (58, 195, 241), edge)
    line([(6, 28), (32, 42), (58, 28)], (124, 239, 255), edge)
    line([(32, 42), (32, 59)], (76, 207, 243), edge)

    # Raised slice, with a bright top and two visible cut edges.
    polygon([(6, 18), (32, 4), (58, 18), (32, 32)], (192, 249, 255), (48, 196, 234))
    polygon([(6, 18), (32, 32), (32, 37), (6, 23)], (39, 171, 216), (15, 110, 166))
    polygon([(32, 32), (58, 18), (58, 23), (32, 37)], (18, 116, 170), (13, 74, 122))
    line([(6, 18), (6, 23), (32, 37), (58, 23), (58, 18)], (72, 198, 235), edge)
    line([(6, 18), (32, 4), (58, 18), (32, 32), (6, 18)], (166, 246, 255), edge)

    blocks = canvas.reshape(size, samples, size, samples, 4)
    sums = blocks.sum(axis=(1, 3), dtype=np.uint16)
    occupied = sums[:, :, 3] / 255
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :, :3] = np.rint(sums[:, :, :3] / np.maximum(occupied[:, :, None], 1))
    pixels[:, :, 3] = np.rint(sums[:, :, 3] / samples**2)
    return pixels


def png(pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    size = len(pixels)
    rows = b''.join(b'\0' + row.tobytes() for row in pixels)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows))
            + chunk(b'IEND', b''))


def main():
    images = [(size, png(render(size))) for size in SIZES]
    offset = 6 + 16 * len(images)
    directory = []
    for size, data in images:
        dimension = size % 256
        directory.append(struct.pack('<BBBBHHII', dimension, dimension, 0, 0, 1, 32, len(data), offset))
        offset += len(data)

    target = Path(__file__).resolve().parents[1] / 'src/SlicerPro/Assets'
    target.mkdir(exist_ok=True)
    (target / 'app.ico').write_bytes(struct.pack('<HHH', 0, 1, len(images))
                                    + b''.join(directory) + b''.join(data for _, data in images))
    (target / 'brand.png').write_bytes(images[-1][1])


if __name__ == '__main__':
    main()
