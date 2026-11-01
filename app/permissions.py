def item_access_mode(item, user) -> str:
    if item is None:
        return "denied"

    is_owner = user is not None and user["id"] == item["seller_id"]
    is_admin = user is not None and user["role"] == "admin"

    if not item["is_removed"]:
        if item["status"] == "unavailable":
            return "paused_owner" if (is_owner or is_admin) else "paused_public"
        return "full"

    if item["removed_by"] == "admin":
        return "removed_admin" if (is_owner or is_admin) else "denied"
    return "removed_seller" if is_admin else "denied"
