# Dual RTSP Camera Setup

## Camera Layout

- `cam_indoor`: Living Room
- `cam_door`: Door Entrance Area

## Runtime Variables

Set before launching backend:

- `CAMERA_INDOOR_RTSP`
- `CAMERA_DOOR_RTSP`
- `CAMERA_PROCESSING_FPS` (recommended 10-15)

Example:

```bash
export CAMERA_INDOOR_RTSP="rtsp://user:pass@192.168.1.40:554/stream1"
export CAMERA_DOOR_RTSP="rtsp://user:pass@192.168.1.41:554/stream1"
python backend/run_backend.py
```

## Processing Model

- Streams are kept open for health and buffering.
- Heavy analysis is trigger-based.
- Fire confirmation uses indoor camera snapshots when smoke events occur.
