# GitHub + LinkedIn public release checklist

## Before pushing to GitHub
- [ ] Use the public source project only; **never add** real `go2rtc.yaml`,
      Xiaomi tokens, passwords, one-time codes, account IDs or real device URLs.
- [ ] Exclude `private_data/`, event photos/videos, any face photos,
      private IP-address details and model weights.
- [ ] Check `git status --short` and `git diff --cached` before each push.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Use **only simulated** images in demo screenshots, label them DEMO.
- [ ] Add a license after reviewing compatibility with go2rtc and Ultralytics
      dependencies (their licenses may impose conditions on redistribution).
- [ ] Rewrite only verified accomplishments as "working"; don't call real
      C301 integration complete until it's personally tested.

## Suggested public repo settings

**Repository name:** `C301-AI-Security-Monitor`

**Description:** `Windows-based local AI camera dashboard for Xiaomi C301: Python, OpenCV, YOLO object detection, 2D motion map, event snapshots and go2rtc bridge (work in progress).`

**GitHub topics:** `python`, `opencv`, `computer-vision`, `iot`, `xiaomi`, `yolo`, `go2rtc`, `home-security`

**Suggested first commit message:**
`feat: bootstrap C301 AI monitor with demo UI and local event logging`

## LinkedIn
- [ ] Upload a screenshot from `assets/demo-dashboard.png` marked DEMO.
- [ ] Add the public GitHub URL only after successful creation.
- [ ] Include real camera footage **only with permission**, after hiding private details.
- [ ] Describe C301 integration as "planned/testing" until validated.
- [ ] Cite libraries and credit open-source maintainers.
