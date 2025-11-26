"""FastMCP service backed by Amap(Gaode) APIs for trip planning and POI search."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(override=False)

AMAP_API_KEY = os.getenv("AMAP_API_KEY")
AMAP_PLACE_URL = "https://restapi.amap.com/v3/place/text"

app = FastMCP("amap-service")


@dataclass
class MCPResponse:
    ok: bool
    data: Optional[Dict[str, object]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"ok": self.ok}
        if self.data is not None:
            payload["data"] = self.data
        if self.error:
            payload["error"] = self.error
        return payload


def _require_api_key() -> str:
    if not AMAP_API_KEY:
        raise RuntimeError(
            "AMAP_API_KEY is not configured. Please set it in your .env or environment variables."
        )
    return AMAP_API_KEY


def _amap_get(params: Dict[str, str]) -> Dict[str, object]:
    params = {**params, "key": _require_api_key(), "extensions": "base", "output": "JSON"}
    resp = requests.get(AMAP_PLACE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if str(data.get("status")) != "1":
        raise RuntimeError(f"Amap API error: {data.get('info')}")
    return data


class PlanTripSchema(BaseModel):
    city: str = Field(..., description="City or destination name, e.g. 北京/Shanghai.")
    start_date: Optional[str] = Field(
        None, description="Trip start date (YYYY-MM-DD). Defaults to tomorrow."
    )
    days: int = Field(3, ge=1, le=14, description="Number of travel days.")
    interests: Optional[List[str]] = Field(
        None, description="Optional interest keywords, e.g. ['美食', '博物馆']."
    )


class PoiSearchSchema(BaseModel):
    city: Optional[str] = Field(None, description="City to search in.")
    keywords: str = Field(..., description="Keywords to search POIs.")
    limit: int = Field(10, ge=1, le=25, description="Maximum POIs to return.")


@app.tool(name="plan_trip")
def plan_trip(
    city: str,
    days: int = 3,
    start_date: Optional[str] = None,
    interests: Optional[List[str]] = None,
) -> Dict[str, object]:
    """Plan a multi-day itinerary using Amap POIs."""
    try:
        params = PlanTripSchema(city=city, days=days, start_date=start_date, interests=interests)
        pois = _collect_pois(params.city, params.interests or [], params.days * 4)
        itinerary = _build_itinerary(pois, params.days, params.start_date)
        overview = [
            {
                "name": poi["name"],
                "address": poi.get("address"),
                "category": poi.get("type"),
                "location": poi.get("location"),
            }
            for poi in pois[: min(len(pois), params.days * 5)]
        ]
        return MCPResponse(
            ok=True,
            data={
                "city": params.city,
                "days": params.days,
                "start_date": itinerary["start_date"],
                "itinerary": itinerary["days"],
                "poi_overview": overview,
            },
        ).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


@app.tool(name="poi_search")
def poi_search(city: Optional[str], keywords: str, limit: int = 10) -> Dict[str, object]:
    """Search POIs in a city using Amap text search."""
    try:
        params = PoiSearchSchema(city=city, keywords=keywords, limit=limit)
        pois = _collect_pois(params.city or "", [params.keywords], params.limit)
        data = [
            {
                "name": poi["name"],
                "address": poi.get("address"),
                "category": poi.get("type"),
                "location": poi.get("location"),
                "distance": poi.get("distance"),
            }
            for poi in pois[: params.limit]
        ]
        return MCPResponse(ok=True, data={"city": params.city, "keywords": params.keywords, "pois": data}).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


def _collect_pois(city: str, interests: List[str], limit: int) -> List[Dict[str, str]]:
    if not city:
        city_code = ""
    else:
        city_code = city

    collected: List[Dict[str, str]] = []
    queries = interests or ["景点", "美食", "文化"]
    for keyword in queries:
        try:
            data = _amap_get(
                {
                    "city": city_code,
                    "keywords": keyword,
                    "types": "110000|050000|060000",
                    "children": "1",
                    "offset": "10",
                    "page": "1",
                }
            )
            collected.extend(data.get("pois", []))
        except Exception:
            continue
        if len(collected) >= limit:
            break
    # deduplicate by id
    unique = {}
    for poi in collected:
        poi_id = poi.get("id") or poi.get("name")
        if poi_id not in unique:
            unique[poi_id] = poi
    return list(unique.values())[:limit]


def _build_itinerary(pois: List[Dict[str, str]], days: int, start_date: Optional[str]) -> Dict[str, object]:
    day_plan: List[Dict[str, object]] = []
    if start_date:
        try:
            current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            current_date = (datetime.utcnow() + timedelta(days=1)).date()
    else:
        current_date = (datetime.utcnow() + timedelta(days=1)).date()

    slot_labels = ["上午", "下午", "晚上"]
    idx = 0
    for day in range(days):
        activities: List[Dict[str, str]] = []
        for slot in slot_labels:
            if idx >= len(pois):
                break
            poi = pois[idx]
            idx += 1
            activities.append(
                {
                    "time_slot": slot,
                    "name": poi["name"],
                    "address": poi.get("address"),
                    "category": poi.get("type"),
                    "notes": "提前 15 分钟到达，合理安排交通。",
                }
            )
        day_plan.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "activities": activities,
            }
        )
        current_date += timedelta(days=1)
    return {"start_date": day_plan[0]["date"] if day_plan else None, "days": day_plan}


if __name__ == "__main__":
    if not AMAP_API_KEY:
        raise SystemExit("AMAP_API_KEY not configured. Please set it before running the Amap MCP service.")
    app.run()

