# -*- coding: utf-8 -*-
from datetime import datetime
import base64
from pathlib import Path
import sys

import cv2
import numpy as np
import segno


def build_login_qrcode_path(account_file: str, suffix: str = "login_qrcode") -> Path:
    account_path = Path(account_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return account_path.with_name(f"{account_path.stem}_{suffix}_{timestamp}.png")


def save_data_url_image(data_url: str, output_path: Path) -> Path:
    if not data_url.startswith("data:image/"):
        raise ValueError("QR code URL is not a data:image payload")

    header, encoded = data_url.split(",", 1)
    if ";base64" not in header:
        raise ValueError("QR code image is not base64 encoded")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(encoded))
    return output_path


def remove_qrcode_file(qrcode_path: Path | None) -> bool:
    if qrcode_path and qrcode_path.exists():
        qrcode_path.unlink()
        return True
    return False


def decode_qrcode_from_path(qrcode_path: Path) -> str | None:
    # cv2.imread is unreliable for non-ASCII paths on Windows, so prefer numpy+imdecode
    image = None
    try:
        data = np.fromfile(str(qrcode_path), dtype=np.uint8)
        if data.size > 0:
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        image = None
    if image is None:
        image = cv2.imread(str(qrcode_path))
    if image is None:
        return None

    detector = cv2.QRCodeDetector()
    qrcode_content, _, _ = detector.detectAndDecode(image)
    return qrcode_content or None


def _print_ascii_qrcode(qrcode) -> None:
    border = 1
    rows = list(qrcode.matrix)
    empty_line = "  " * (len(rows[0]) + border * 2)
    print(empty_line)
    for row in rows:
        line = ["  "] * border
        line.extend("##" if cell else "  " for cell in row)
        line.extend(["  "] * border)
        print("".join(line))
    print(empty_line)


def print_terminal_qrcode(
    qrcode_content: str,
    qrcode_path: Path,
    app_name: str,
    compact: bool = True,
    border: int = 0,
) -> None:
    print()
    print(f"Scan the QR code below with {app_name}:")
    qrcode = segno.make(qrcode_content, error="L", boost_error=False)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        qrcode.terminal(compact=compact, border=border)
    except (UnicodeEncodeError, OSError):
        print("This terminal cannot show Unicode QR characters, falling back to ASCII:")
        _print_ascii_qrcode(qrcode)
    print("On Windows use Windows Terminal (UTF-8 capable, renders the full QR code)")
    print(f"Otherwise open {qrcode_path} and scan it")
    print()
