"""Vai trò đồ (`FurnitureRole` của FE) ↔ `type` hồ sơ mẫu, vai trò cần theo công năng phòng, cỡ điển hình."""

from collections.abc import Iterable
from typing import Final

# Vai trò → type hồ sơ (hợp đồng AID-01); thứ tự khoá = thứ tự chuẩn khi trả vai trò.
ROLE_TYPE: Final[dict[str, str]] = {
    "doubleBed": "bed",
    "singleBed": "bed",
    "closet": "wardrobe",
    "dresser": "wardrobe",
    "bookshelf": "bookshelf",
    "diningChair": "diningChair",
    "armchair": "armchair",
    "sofa": "sofa",
    "nightstand": "nightstand",
    "coffeeTable": "coffeeTable",
    "desk": "desk",
    "diningTable": "diningTable",
    "fridge": "fridge",
    "counter": "kitchenCabinet",
    "toilet": "toilet",
    "bathtub": "bathtub",
    "shower": "shower",
    "basin": "basin",
    "washer": "washer",
    "plant": "plant",
    "smallPlant": "plant",
    "rug": "rug",
    "roundRug": "rug",
}

# Cỡ điển hình (w theo X, d theo Z, mm) để lọc ứng viên ±30 % khi không có cỡ chỗ đặt thật.
TYPICAL_SIZE_MM: Final[dict[str, tuple[float, float]]] = {
    "doubleBed": (1800, 2100),
    "singleBed": (1000, 2000),
    "closet": (1600, 600),
    "dresser": (1000, 450),
    "bookshelf": (900, 350),
    "diningChair": (450, 500),
    "armchair": (800, 800),
    "sofa": (2000, 900),
    "nightstand": (450, 400),
    "coffeeTable": (1000, 550),
    "desk": (1200, 600),
    "diningTable": (1400, 800),
    "fridge": (700, 700),
    "counter": (1800, 600),
    "toilet": (400, 700),
    "bathtub": (1700, 750),
    "shower": (900, 900),
    "basin": (600, 450),
    "washer": (600, 600),
    "plant": (450, 450),
    "smallPlant": (250, 250),
    "rug": (2000, 1400),
    "roundRug": (1500, 1500),
}

# Món chính: lấy 12 ứng viên; món phụ: 4.
MAIN_ROLES: Final[frozenset[str]] = frozenset({"doubleBed", "singleBed", "sofa", "diningTable", "closet", "desk"})

USAGE_ROLES: Final[dict[str, tuple[str, ...]]] = {
    "bedroom": ("doubleBed", "nightstand", "closet"),
    "livingRoom": ("sofa", "coffeeTable", "armchair", "plant"),
    "kitchen": ("diningTable", "diningChair", "fridge", "counter"),
    "bathroom": ("toilet", "basin", "shower"),
    "loggia": ("washer", "plant"),
    "utility": ("washer", "plant"),
}


def roles_for_usages(usages: Iterable[str]) -> tuple[str, ...]:
    """Vai trò cần chọn mẫu cho tập công năng phòng; không trùng, theo thứ tự `ROLE_TYPE`. Công năng lạ bị lờ."""
    need = {r for u in usages for r in USAGE_ROLES.get(u, ())}
    return tuple(r for r in ROLE_TYPE if r in need)
