"""NO-188: cột `users.role` dùng đúng `ROLES` của gương quyền, không khai lại."""

from packages.db.models import auth
from packages.domain import permissions


def test_users_roles__is_the_permissions_mirror() -> None:
    """`packages.db.models.auth.ROLES` chính là `packages.domain.permissions.ROLES`."""
    assert vars(auth)["ROLES"] is permissions.ROLES
