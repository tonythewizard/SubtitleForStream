"""Render the SubtitleForStream mark as a multi-resolution Windows icon."""
from pathlib import Path
import struct

from PySide6.QtCore import QBuffer, QIODevice
from app.theme import icon_images


def main():
    root = Path(__file__).resolve().parents[1]
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = []
    for size,image in zip(sizes,icon_images(sizes)):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, 'PNG'):
            raise RuntimeError(f'Esportazione icona fallita ({size}px).')
        images.append(bytes(buffer.data()))
    directory = bytearray(struct.pack('<HHH', 0, 1, len(sizes)))
    offset = 6 + 16 * len(sizes)
    for size, image in zip(sizes, images):
        directory.extend(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0,
                                     1, 32, len(image), offset))
        offset += len(image)
    output = root / 'assets' / 'SubtitleForStream.ico'
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(directory + b''.join(images))


if __name__ == '__main__':
    main()
