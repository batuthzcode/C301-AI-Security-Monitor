# C301 AI Security Monitor — development roadmap

All statuses are evidence-based. Do not describe a feature as verified on the
physical Xiaomi C301 until it has been tested on the user's device.

| Phase | Feature | State |
|---|---|---|
| 0 | Research C301/go2rtc stream integration | Documented, integration untested |
| 1 | Local Windows GUI with RTSP/webcam/video inputs | Implemented, physical camera untested |
| 1 | Synthetic demo, bounding boxes, 2D visualization | Windows demo UI confirmed by user screenshot; actual camera pending |
| 1 | Local JSONL events and saved snapshots | Implemented; end-to-end validation pending |
| 1 | PC speaker spoken alerts | Implemented with fallback; Windows test pending |
| 2 | Actual Xiaomi Home login and C301 live-stream verification | Pending user-side test |
| 2 | Optimize CPU/GPU video latency on target Windows laptop | Pending benchmark |
| 3 | Persistent multi-object IDs / real entry-exit detection | Planned |
| 3 | Arbitrary objects, zones, notification policies | Planned |
| 4 | Camera speaker audio via go2rtc backchannel | Experimental; not guaranteed |
| 4 | Remote notifications, encrypted access | Planned |
| 5 | Standalone always-on host; PC-off use case | Not in current scope |

No face recognition or identity claims in v0.1.
