from typing import Any, Dict, List

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from sub_applications.manager_api.models import SysMenu, SysRole, SysRoleMenu, SysUserRole


def _default_routers() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Dashboard",
            "path": "/",
            "component": "Layout",
            "redirect": "/home",
            "meta": {"title": "Dashboard", "icon": "dashboard", "noCache": False},
            "children": [
                {
                    "name": "Home",
                    "path": "home",
                    "component": "home/index",
                    "meta": {"title": "Home", "icon": "dashboard", "noCache": False},
                }
            ],
        }
    ]


def get_permissions(db: Session, user_id: int) -> List[str]:
    stmt = (
        select(SysMenu.perms)
        .select_from(SysUserRole)
        .join(SysRole, SysRole.role_id == SysUserRole.role_id)
        .join(SysRoleMenu, SysRoleMenu.role_id == SysRole.role_id)
        .join(SysMenu, SysMenu.menu_id == SysRoleMenu.menu_id)
        .where(
            and_(
                SysUserRole.user_id == user_id,
                SysRole.status == "0",
                SysRole.del_flag == "0",
                SysMenu.status == "0",
            )
        )
    )
    permissions = [row[0] for row in db.execute(stmt).all() if row[0]]
    if permissions:
        return sorted(list(set(permissions)))
    return ["*:*:*"]


def _build_menu_tree(menu_rows: List[SysMenu]) -> List[Dict[str, Any]]:
    id_to_node: Dict[int, Dict[str, Any]] = {}
    root_nodes: List[Dict[str, Any]] = []

    for row in menu_rows:
        is_hidden = str(row.visible) != "0"
        menu_type = row.menu_type or "M"
        node: Dict[str, Any] = {
            "name": row.route_name or row.menu_name,
            "path": row.path or "",
            "component": row.component or ("Layout" if menu_type == "M" else ""),
            "hidden": is_hidden,
            "meta": {
                "title": row.menu_name,
                "icon": row.icon or "menu",
                "noCache": bool(row.is_cache),
            },
            "children": [],
        }
        if row.query:
            node["query"] = row.query
        if menu_type == "M":
            node["redirect"] = "noRedirect"
        id_to_node[int(row.menu_id)] = node

    for row in menu_rows:
        node = id_to_node[int(row.menu_id)]
        parent_id = int(row.parent_id or 0)
        if parent_id and parent_id in id_to_node:
            id_to_node[parent_id]["children"].append(node)
        else:
            root_nodes.append(node)

    for node in id_to_node.values():
        if node.get("children"):
            node["alwaysShow"] = True
        else:
            node.pop("children", None)

    return root_nodes


def get_routers(db: Session, user_id: int) -> List[Dict[str, Any]]:
    stmt = (
        select(SysMenu)
        .select_from(SysUserRole)
        .join(SysRole, SysRole.role_id == SysUserRole.role_id)
        .join(SysRoleMenu, SysRoleMenu.role_id == SysRole.role_id)
        .join(SysMenu, SysMenu.menu_id == SysRoleMenu.menu_id)
        .where(
            and_(
                SysUserRole.user_id == user_id,
                SysRole.status == "0",
                SysRole.del_flag == "0",
                SysMenu.status == "0",
                SysMenu.menu_type.in_(["M", "C"]),
            )
        )
        .order_by(SysMenu.parent_id.asc(), SysMenu.order_num.asc(), SysMenu.menu_id.asc())
    )
    menu_rows = [row[0] for row in db.execute(stmt).all()]
    if not menu_rows:
        return _default_routers()
    return _build_menu_tree(menu_rows)
