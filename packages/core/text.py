"""Chuẩn hoá chuỗi người nhập (BE-00 §6): NFC; email so qua `normalize_email` (C16)."""

import unicodedata


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def normalize_email(s: str) -> str:
    return nfc(s).strip().casefold()
