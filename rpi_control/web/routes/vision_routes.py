"""Vision API routes."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])

_mock_vision_status = {
    "camera_connected": True,
    "camera_resolution": "640x480",
    "fps": 30.0,
    "last_detection": None,
    "active_filters": ["red", "blue", "green"],
}

_mock_color_thresholds: Dict[str, Dict[str, int]] = {
    "red": {"h_min": 0, "h_max": 10, "s_min": 100, "s_max": 255, "v_min": 100, "v_max": 255},
    "blue": {"h_min": 100, "h_max": 130, "s_min": 100, "s_max": 255, "v_min": 100, "v_max": 255},
    "green": {"h_min": 40, "h_max": 80, "s_min": 100, "s_max": 255, "v_min": 100, "v_max": 255},
}


@router.get("/status")
async def get_vision_status():
    """Get vision system status."""
    return _mock_vision_status


@router.post("/detect/color")
async def detect_color(data: Dict[str, Any]):
    """Detect a specific color in the camera feed.

    Request body: {color_name: str}
    """
    color_name = data.get("color_name", "red")
    if color_name not in _mock_color_thresholds:
        raise HTTPException(status_code=400, detail=f"Unknown color: {color_name}")

    _mock_vision_status["last_detection"] = datetime.now(timezone.utc)

    return {
        "status": "ok",
        "color": color_name,
        "detections": [
            {
                "x": 320,
                "y": 240,
                "width": 50,
                "height": 50,
                "confidence": 0.95,
                "area": 2500,
            }
        ],
        "count": 1,
    }


@router.post("/detect/apriltag")
async def detect_apriltag(data: Dict[str, Any]):
    """Detect AprilTags in the camera feed."""
    _mock_vision_status["last_detection"] = datetime.now(timezone.utc)

    return {
        "status": "ok",
        "tags": [
            {
                "id": 0,
                "family": "tag36h11",
                "center": {"x": 320, "y": 240},
                "corners": [
                    {"x": 300, "y": 220},
                    {"x": 340, "y": 220},
                    {"x": 340, "y": 260},
                    {"x": 300, "y": 260},
                ],
                "pose": {"x": 0.0, "y": 0.0, "z": 500.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
            }
        ],
        "count": 1,
    }


@router.post("/classify")
async def classify_object(data: Dict[str, Any]):
    """Classify an object in the current view."""
    return {
        "status": "ok",
        "classifications": [
            {"label": "sample_a", "confidence": 0.92},
            {"label": "sample_b", "confidence": 0.45},
            {"label": "sample_c", "confidence": 0.12},
        ],
        "top_prediction": {"label": "sample_a", "confidence": 0.92},
    }


@router.post("/inspect")
async def quality_inspection(data: Dict[str, Any]):
    """Perform quality inspection on the current view."""
    return {
        "status": "ok",
        "inspection": {
            "score": 0.87,
            "defects": [],
            "dimensions": {"width": 25.5, "height": 12.3, "depth": 10.0},
            "passed": True,
        },
    }


@router.get("/stream")
async def video_stream():
    """MJPEG video stream endpoint."""
    # In production, this would stream from the camera
    return StreamingResponse(
        content=iter([b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"]),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/snapshot")
async def get_snapshot():
    """Get the latest camera snapshot."""
    # In production, this would return the actual camera image
    return {
        "status": "ok",
        "message": "No snapshot available in mock mode",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/threshold")
async def set_threshold(data: Dict[str, Any]):
    """Set color detection threshold.

    Request body: {color: str, threshold: {h_min, h_max, s_min, s_max, v_min, v_max}}
    """
    color = data.get("color", "")
    threshold = data.get("threshold", {})

    if not color:
        raise HTTPException(status_code=400, detail="Color name is required")

    _mock_color_thresholds[color] = threshold
    logger.info(f"Threshold set for color '{color}': {threshold}")
    return {"status": "ok", "message": f"Threshold updated for {color}"}