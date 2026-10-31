"""Patched copy of PolymarketData._cursor_scan: identical except the descending
one-second offset walk carries limit=PAGE (as the ascending path does)."""
from polyrea.adapters import polymarket as P
from polyrea.evidence import Coverage

def fixed_cursor_scan(self, url, base_params, *, start, end, adapter, max_rows, ascending_supported=True):
    if ascending_supported:
        return ORIG(self, url, base_params, start=start, end=end, adapter=adapter, max_rows=max_rows, ascending_supported=True)
    sources, pages, total, truncated = [], [], 0, False
    cursor_end = end
    while True:
        params = {**base_params, "limit": P.PAGE, "start": start, "end": cursor_end}
        page, src = self._page(url, params, adapter, cursor_end)
        sources.append(src)
        page = list(reversed(page))
        if len(page) == P.PAGE and page[0].get("timestamp") == page[-1].get("timestamp"):
            ts = page[0]["timestamp"]
            extra = self._offset_walk(url, {**base_params, "start": ts, "end": ts, "limit": P.PAGE}, adapter, ts, sources)  # <- fix
            pages.append(extra)
            total += len(extra)
            if start is not None and ts - 1 < start:
                break
            cursor_end = ts - 1
            continue
        pages.append(page)
        total += len(page)
        if len(page) < P.PAGE:
            break
        if max_rows is not None and total >= max_rows:
            truncated = True
            break
        cursor_end = page[0]["timestamp"]
    rows = P.merge_cursor_pages(list(reversed(pages)))
    return rows, sources, Coverage("partial" if truncated else ("complete" if rows else "empty"), f"{len(rows)} rows")

ORIG = P.PolymarketData._cursor_scan
def install():
    P.PolymarketData._cursor_scan = fixed_cursor_scan
def uninstall():
    P.PolymarketData._cursor_scan = ORIG
