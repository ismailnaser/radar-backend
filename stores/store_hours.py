"""حساب مفتوح/مغلق من جدول أسبوعي ومعلومات المنطقة الزمنية."""

from __future__ import annotations

from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def _js_weekday(dt: datetime) -> int:
    """0=الأحد … 6=السبت (مثل JavaScript getDay)."""
    pw = dt.weekday()  # اثنين=0 … أحد=6
    return (pw + 1) % 7


def _parse_hhmm(s: str) -> int | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    parts = s.split(':')
    if len(parts) != 2:
        return None
    try:
        h = int(parts[0])
        m = int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return h * 60 + m
    except (TypeError, ValueError):
        return None


def is_store_open_now(weekly: dict | None, tz_name: str | None) -> bool | None:
    """
    weekly: مفاتيح نصية "0".."6" (أحد=0)، قيمة: [{"start":"09:00","end":"17:00"}, ...]
    يُرجع True/False أو None إذا لا يمكن الحساب (لا جدول).
    """
    if not weekly or not isinstance(weekly, dict):
        return None
    if ZoneInfo is None:
        return None
    try:
        tz = ZoneInfo((tz_name or 'Asia/Gaza').strip() or 'Asia/Gaza')
    except Exception:
        try:
            tz = ZoneInfo('Asia/Gaza')
        except Exception:
            return None

    now = datetime.now(tz)
    wd = str(_js_weekday(now))
    intervals = weekly.get(wd)
    if intervals is None:
        intervals = weekly.get(int(wd)) if wd.isdigit() else None
    if not intervals:
        return False

    cur = now.hour * 60 + now.minute

    for it in intervals:
        if not isinstance(it, dict):
            continue
        st = _parse_hhmm(it.get('start') or '')
        en = _parse_hhmm(it.get('end') or '')
        if st is None or en is None:
            continue
        if st <= en:
            if st <= cur < en:
                return True
        else:
            # يمرّ الليل (مثلاً 22:00–02:00)
            if cur >= st or cur < en:
                return True
    return False
