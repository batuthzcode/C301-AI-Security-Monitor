"""Experimental Xiaomi MISS one-step PTZ patch for go2rtc 1.9.15 source (v2).

Does not change camera firmware, original go2rtc exe or yaml.
Works against the AUDIO-PATCHED go2rtc source at LOCALAPPDATA.
PR #2531 describes command 0x112 operation 1..4 on *other* Xiaomi models;
not hardware-tested on C301. Motor ACK is not movement verification.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

HOME = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')))
WORK = HOME / 'C301-go2rtc-audio-fix'
REPO = WORK / 'go2rtc-1.9.15'
MARKER = '// C301_TI_EXPERIMENTAL_PTZ_V1'

PATCHES = [
    (
        'pkg/xiaomi/miss/client.go',
        'type Packet struct {',
        '''// C301_TI_EXPERIMENTAL_PTZ_V1
// Sends one motor step; exact C301 support is not yet validated.
func (c *Client) Motor(operation int) error {
    if operation < 1 || operation > 4 {
        return fmt.Errorf("xiaomi motor: invalid operation %d", operation)
    }
    data := binary.BigEndian.AppendUint32(nil, cmdMotorReq)
    data = fmt.Appendf(data, `{"operation":%d}`, operation)
    return c.WriteCommand(data)
}

''',
    ),
    (
        'pkg/xiaomi/miss/producer.go',
        'const timestamp40ms',
        '''// C301_TI_EXPERIMENTAL_PTZ_V1
func (p *Producer) Motor(operation int) error {
    return p.client.Motor(operation)
}

''',
    ),
    (
        'internal/streams/stream.go',
        'func NewStream(source any) *Stream {',
        '''// C301_TI_EXPERIMENTAL_PTZ_V1
// Reuses already-connected Xiaomi camera; do not dial a second P2P session.
func (s *Stream) XiaomiMotor(operation int) error {
    if operation < 1 || operation > 4 {
        return fmt.Errorf("xiaomi motor: invalid operation %d", operation)
    }
    s.mu.Lock()
    producers := append([]*Producer(nil), s.producers...)
    s.mu.Unlock()
    for _, producer := range producers {
        producer.mu.Lock()
        conn := producer.conn
        producer.mu.Unlock()
        if mover, ok := conn.(interface { Motor(int) error }); ok {
            return mover.Motor(operation)
        }
    }
    return fmt.Errorf("xiaomi motor: no active PTZ capable camera connection")
}

''',
    ),
    (
        'internal/xiaomi/xiaomi.go',
        'func apiDeviceList(w http.ResponseWriter, r *http.Request) {',
        '''// C301_TI_EXPERIMENTAL_PTZ_V1
// Local API only; the user's go2rtc API should stay bound to 127.0.0.1.
func apiXiaomiMotor(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        http.Error(w, "POST required", http.StatusMethodNotAllowed)
        return
    }
    streamName := r.URL.Query().Get("src")
    if streamName == "" {
        http.Error(w, "missing src", http.StatusBadRequest)
        return
    }
    operation, err := strconv.Atoi(r.URL.Query().Get("operation"))
    if err != nil || operation < 1 || operation > 4 {
        http.Error(w, "operation must be 1..4", http.StatusBadRequest)
        return
    }
    stream := streams.Get(streamName)
    if stream == nil {
        http.Error(w, "stream not found", http.StatusNotFound)
        return
    }
    if err := stream.XiaomiMotor(operation); err != nil {
        http.Error(w, err.Error(), http.StatusConflict)
        return
    }
    w.WriteHeader(http.StatusNoContent)
}

''',
    ),
]

def modify(content: str, path: str, anchor: str, patch: str) -> str:
    if MARKER in content:
        print('[Ti PTZ] Already patched:', path)
        return protect_api(content) if path == 'internal/xiaomi/xiaomi.go' else content
    if content.count(anchor) != 1:
        raise RuntimeError(f'Could not match unique anchor in {path}: {anchor}')
    content = content.replace(anchor, patch + anchor, 1)
    if path == 'internal/streams/stream.go':
        content = content.replace('import (\n', 'import (\n    "fmt"\n', 1)
    if path == 'internal/xiaomi/xiaomi.go':
        content = content.replace('import (\n', 'import (\n    "strconv"\n', 1)
        anchor2 = 'api.HandleFunc("api/xiaomi", apiXiaomi)'
        if content.count(anchor2) != 1:
            raise RuntimeError('api/xiaomi registration anchor missing')
        content = content.replace(anchor2, anchor2 + '\n    api.HandleFunc("api/xiaomi/motor", apiXiaomiMotor)', 1)

    if path == 'internal/xiaomi/xiaomi.go':
        content = protect_api(content)
    return content


def protect_api(content: str) -> str:
    # The new motor HTTP endpoint is reachable only from this PC.
    if '// C301_TI_PTZ_LOCAL_ONLY' in content:
        return content
    marker = 'func apiXiaomiMotor(w http.ResponseWriter, r *http.Request) {'
    if marker not in content:
        raise RuntimeError('Motor API handler not found for loopback protection')
    guard = """
    // C301_TI_PTZ_LOCAL_ONLY
    host, _, splitErr := net.SplitHostPort(r.RemoteAddr)
    ip := net.ParseIP(host)
    if splitErr != nil || ip == nil || !ip.IsLoopback() {
        http.Error(w, "local requests only", http.StatusForbidden)
        return
    }
"""
    content = content.replace(marker, marker + guard, 1)
    content = content.replace('import (\n', 'import (\n    "net"\n', 1)
    return content


def main():
    if not (REPO / 'go.mod').exists():
        raise SystemExit(f'Missing go2rtc source tree: {REPO}')
    cs2 = REPO / 'pkg/xiaomi/miss/cs2/conn.go'
    if 'copy(req[offset+hdrSize:], payload)' not in cs2.read_text(encoding='utf-8'):
        raise SystemExit('Audio fix missing in source tree. Refusing to build a binary without the working speaker fix.')
    updates = []
    for path, anchor, patch in PATCHES:
        file = REPO / path
        original = file.read_text(encoding='utf-8')
        updated = modify(original, path, anchor, patch)
        updates.append((file, original, updated))

    for file, original, updated in updates:
        if updated == original:
            continue
        backup = file.with_suffix(file.suffix + '.before_ti_ptz')
        if not backup.exists():
            backup.write_text(original, encoding='utf-8')
        file.write_text(updated, encoding='utf-8')
    try:
        subprocess.run(['gofmt', '-w', *[str(f) for f, _, _ in updates]], check=True)
        subprocess.run(['go', 'test', '-run', '^$', './pkg/xiaomi/miss', './internal/xiaomi', './internal/streams'], cwd=REPO, check=True)
        target = WORK / 'go2rtc_ti_ptz_experimental.exe'
        subprocess.run(['go', 'build', '-trimpath', '-o', str(target), '.'], cwd=REPO, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Compile or tests failed: {exc}; existing working go2rtc exe was not modified') from exc
    print('[Ti PTZ] EXE created:', target)
    print('[Ti PTZ] Motor HTTP route is loopback only.')
    print('[Ti PTZ] C301 motor behavior NOT YET HARDWARE VERIFIED. Backup old exe; test separately.')

if __name__ == '__main__':
    main()
