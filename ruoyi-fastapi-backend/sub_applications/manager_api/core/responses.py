from typing import Any, Dict, Optional


def xz_ok(data: Any = None, msg: str = "success") -> Dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


def xz_error(code: int, msg: str, data: Any = None) -> Dict[str, Any]:
    return {"code": code, "msg": msg, "data": data}


def ruoyi_ok(
    data: Any = None,
    msg: str = "Operation success",
    code: int = 200,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"code": code, "msg": msg}
    if data is not None:
        body["data"] = data
    if extra:
        body.update(extra)
    return body


def ruoyi_error(msg: str = "Operation failed", code: int = 500) -> Dict[str, Any]:
    return {"code": code, "msg": msg}
