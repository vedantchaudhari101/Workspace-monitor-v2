"""Time-series occupancy forecasting engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.occupancy_snapshot import OccupancySnapshot

logger = logging.getLogger(__name__)

async def predict_occupancy_trend(
    db: AsyncSession,
    building_id: UUID,
    days_ahead: int = 7,
) -> list[dict]:
    """Predict hourly occupancy rate and seat counts for the next days_ahead days."""
    # Query building-level snapshots (where floor_id and startup_id are None)
    query = (
        select(OccupancySnapshot)
        .where(
            OccupancySnapshot.building_id == building_id,
            OccupancySnapshot.floor_id.is_(None),
            OccupancySnapshot.startup_id.is_(None),
        )
        .order_by(OccupancySnapshot.snapshot_time.asc())
    )
    res = await db.execute(query)
    snapshots = res.scalars().all()

    if not snapshots:
        logger.warning(f"No historical snapshots found for building {building_id} to forecast.")
        return []

    # Prepare DataFrame
    data = [
        {
            "timestamp": s.snapshot_time,
            "occupancy_rate": s.occupancy_rate,
            "total_seats": s.total_seats,
            "occupied_seats": s.occupied_seats,
        }
        for s in snapshots
    ]
    df = pd.DataFrame(data)

    # Ensure timezone-aware timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Determine last timestamp
    last_time = df["timestamp"].max()
    if pd.isna(last_time):
        last_time = datetime.now(timezone.utc)

    # Generate future hourly timestamps
    future_timestamps = [
        last_time + timedelta(hours=i)
        for i in range(1, days_ahead * 24 + 1)
    ]

    # Calculate seasonal patterns (day of week, hour of day)
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["hour"] = df["timestamp"].dt.hour

    grouped = df.groupby(["day_of_week", "hour"])[["occupancy_rate", "total_seats"]].mean().reset_index()

    # Fit linear trend to occupancy rate
    df["sec"] = df["timestamp"].view("int64") // 10**9

    if len(df) >= 2:
        try:
            slope, _ = np.polyfit(df["sec"], df["occupancy_rate"], 1)
        except Exception:
            slope = 0.0
    else:
        slope = 0.0

    predictions = []
    latest_total_seats = int(df["total_seats"].iloc[-1]) if not df.empty else 0
    overall_mean_rate = df["occupancy_rate"].mean() if not df.empty else 0.0

    for ft in future_timestamps:
        dow = ft.weekday()
        hr = ft.hour

        # Find historical match for seasonal pattern
        match = grouped[(grouped["day_of_week"] == dow) & (grouped["hour"] == hr)]
        if not match.empty:
            seasonal_rate = match["occupancy_rate"].values[0]
            pred_total = int(match["total_seats"].values[0])
        else:
            seasonal_rate = overall_mean_rate
            pred_total = latest_total_seats

        # Apply linear trend component relative to the last timestamp (capped to avoid wild deviations)
        sec_diff = (ft - last_time).total_seconds()
        trend_effect = np.clip(slope * sec_diff, -25.0, 25.0)

        pred_rate = np.clip(seasonal_rate + trend_effect, 0.0, 100.0)
        pred_occupied = int(round((pred_rate / 100.0) * pred_total))

        predictions.append({
            "timestamp": ft,
            "predicted_occupancy_rate": round(float(pred_rate), 2),
            "predicted_occupied_seats": int(pred_occupied),
            "total_seats": int(pred_total),
        })

    return predictions
