"""
POC microservice for on-demand “Python insights” callable from Salesforce Agent actions.

POST /v1/insights JSON body:
  reportType (str, optional): e.g. summary, dated_insight
  context / contextJson (object or JSON string): pass **reportDate** (or asOfDate / date)
    as **YYYY-MM-DD** so Python can anchor the sample analytics to that calendar day.

Returns JSON with summaryText plus structured insights.
"""

from __future__ import annotations

import calendar
import json
import os
import re
import statistics
from datetime import date
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request

APP = FastAPI(title="On-demand insights POC", version="0.2.0")
API_KEY = (os.environ.get("ON_DEMAND_INSIGHTS_API_KEY") or "").strip()

_DATE_KEYS = ("reportDate", "asOfDate", "date", "forDate")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _require_key(request: Request) -> None:
    if not API_KEY:
        return
    got = request.headers.get("X-Insights-Api-Key", "")
    if got != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _parse_date_value(raw: Any) -> date:
    if raw is None:
        raise ValueError("empty date")
    s = str(raw).strip()
    if not s:
        raise ValueError("empty date")
    if not _ISO_DATE.match(s[:10]):
        raise ValueError(f"expected YYYY-MM-DD, got {s!r}")
    return date.fromisoformat(s[:10])


def _extract_report_date(context: dict[str, Any], payload: dict[str, Any]) -> date | None:
    top = payload.get("reportDate") or payload.get("report_date")
    if top is not None and str(top).strip():
        return _parse_date_value(top)
    for k in _DATE_KEYS:
        if k in context and context[k] is not None and str(context[k]).strip():
            return _parse_date_value(context[k])
    return None


def _sample_series(seed: str) -> list[float]:
    """Deterministic pseudo-series from seed (stands in for warehouse rows)."""
    n = len(seed) % 7 + 5
    out: list[float] = []
    acc = sum(ord(c) for c in seed) % 100
    for i in range(n):
        acc = (acc * 31 + i * 7 + ord(seed[i % len(seed)])) % 200
        out.append(float(50 + acc % 80) + (acc % 7) / 10.0)
    return out


def _calendar_facts(d: date) -> dict[str, Any]:
    q = (d.month - 1) // 3 + 1
    last = date(d.year, 12, 31)
    days_left_in_year = (last - d).days
    return {
        "isoDate": d.isoformat(),
        "weekday": d.strftime("%A"),
        "isoCalendarYear": d.isocalendar().year,
        "isoWeekNumber": d.isocalendar().week,
        "calendarQuarter": q,
        "calendarQuarterLabel": f"Calendar Q{q} {d.year}",
        "dayOfYear": d.timetuple().tm_yday,
        "daysInMonth": calendar.monthrange(d.year, d.month)[1],
        "daysRemainingInYear": days_left_in_year,
    }


def _metric_for_day(d: date) -> dict[str, float]:
    """Toy KPIs anchored to ordinal date (swap for warehouse SQL later)."""
    o = d.toordinal()
    return {
        "toyDailyIndex": float((o * 7919 + d.day * 97) % 10_000) / 100.0,
        "toyMomentum": float(((o >> 3) ^ (d.year % 63)) % 144) / 10.0,
    }


def _insights_for(report_type: str, context: dict[str, Any], report_day: date | None) -> dict[str, Any]:
    rtype = (report_type or "summary").strip().lower()

    dims = ", ".join(f"{k}={context[k]}" for k in sorted(context) if k not in _DATE_KEYS and context[k])

    seed_parts: list[str] = [rtype, json.dumps(context, sort_keys=True, default=str)]
    date_block: dict[str, Any] | None = None
    if report_day is not None:
        seed_parts.append(report_day.isoformat())
        date_block = {"calendar": _calendar_facts(report_day), "metrics": _metric_for_day(report_day)}
    seed = "|".join(seed_parts)

    series = _sample_series(seed or "default")
    mean_v = statistics.mean(series)
    stdev_v = statistics.pstdev(series) if len(series) > 1 else 0.0

    if rtype == "dated_insight" and report_day is None:
        raise ValueError(
            "reportType 'dated_insight' requires reportDate (YYYY-MM-DD) in context JSON, "
            f"via one of: {', '.join(_DATE_KEYS)}"
        )

    summary = (
        f"Python POC report ({rtype}): synthesized metric sample mean={mean_v:.2f}, "
        f"stdev={stdev_v:.2f}, n={len(series)}."
    )
    if report_day is not None:
        summary += f" Anchored calendar date: **{report_day.isoformat()}** ({report_day.strftime('%A')})."
    if dims:
        summary += f" Other filters: {dims}."

    if report_day is None and rtype in ("dated_insight", "summary"):
        summary += " Tip: include `reportDate` in context (YYYY-MM-DD) so insights anchor to user-chosen date."

    out_insights: dict[str, Any] = {
        "sampleValues": series,
        "statistics": {"mean": mean_v, "stdevPopulation": stdev_v, "n": len(series)},
        "contextEcho": context,
        "reportDateEffective": report_day.isoformat() if report_day else None,
    }
    if date_block is not None:
        out_insights["dateAnchoredInsights"] = date_block

    return {
        "version": "poc-0.2",
        "engine": "cpython-microservice",
        "reportType": rtype,
        "summaryText": summary,
        "insights": out_insights,
    }


@APP.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "requiresApiKey": bool(API_KEY)}


@APP.post("/v1/insights")
def insights(request: Request, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    _require_key(request)
    report_type = str(payload.get("reportType") or payload.get("report_type") or "summary")

    raw_ctx = payload.get("context") or payload.get("contextJson")
    context: dict[str, Any]
    if raw_ctx is None:
        context = {}
    elif isinstance(raw_ctx, str):
        try:
            parsed = json.loads(raw_ctx)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"contextJson must be JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="contextJson must deserialize to an object")
        context = parsed
    elif isinstance(raw_ctx, dict):
        context = raw_ctx
    else:
        raise HTTPException(status_code=400, detail="context must be object or JSON string")

    try:
        report_day = _extract_report_date(dict(context), payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        return _insights_for(report_type, context, report_day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def main() -> None:
    import uvicorn

    host = os.environ.get("INSIGHTS_HOST", "0.0.0.0")
    port = int(os.environ.get("INSIGHTS_PORT", "8890"))
    uvicorn.run(APP, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
