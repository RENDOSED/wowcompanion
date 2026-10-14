"""
LibSerpix 화면 수신기 (Windows용, 파이썬)

WoW 화면 좌상단에 그려진 LibSerpix 픽셀 열을 읽어서 JSON 한 줄씩 출력한다.
디코딩 규칙은 libserpix_rs(Rust) 소스를 따른 것이다.

설치:  pip install mss numpy cbor2
실행:  python serpix_reader.py
       python serpix_reader.py --debug          (실패 사유도 출력)
       python serpix_reader.py --title "World of Warcraft"

게임은 창 모드 또는 전체 창 모드로 실행하고, 창이 최소화되거나 다른 창에 가려지면 안 된다.
"""
import argparse
import ctypes
import json
import time
from collections import Counter

import cbor2
import numpy as np

ANCHOR = (42, 0, 69)      # #2a0045
COL_H = 10                # 열 높이: 앵커 2 + 데이터 6 + 앵커 2
VOTE_ROWS = slice(1, 8)   # 열 안에서 다수결로 색을 정하는 행 (Rust 원본과 동일)


def _anchor_mask(img):
    return (img[..., 0] == ANCHOR[0]) & (img[..., 1] == ANCHOR[1]) & (img[..., 2] == ANCHOR[2])


def _column_to_pixel(col):
    """열 하나(행들 x RGB)를 대표 색 하나로. 같은 색이 3개 미만이면 실패."""
    counts = Counter(tuple(p) for p in col.tolist())
    px, n = counts.most_common(1)[0]
    return px if n >= 3 else None


def decode_frame(img):
    """
    img: 높이 x 너비 x 3 (RGB, uint8) 배열
    반환: (dict, 원본 바이트, None)  성공
          (None, None, 실패 사유)    실패
    """
    mask = _anchor_mask(img)
    flat = np.flatnonzero(mask)
    if flat.size == 0:
        return None, None, "앵커 없음"
    y0, x0 = divmod(int(flat[0]), img.shape[1])
    crop = img[y0:, x0:]
    m = mask[y0:, x0:]
    if crop.shape[0] < COL_H or crop.shape[1] < 4:
        return None, None, "캡처 영역이 너무 작음"

    # 위·아래가 앵커 색인 열 찾기
    xs = np.flatnonzero(m[0, :-1] & m[COL_H - 1, :-1]).tolist()
    # WoW가 1픽셀 열을 2픽셀로 그리는 경우 중복 제거 (Rust 원본과 동일)
    keep = [x for i, x in enumerate(xs) if i == len(xs) - 1 or x + 1 != xs[i + 1]]

    pixels = []
    for x in keep:
        px = _column_to_pixel(crop[VOTE_ROWS, x])
        if px is None:
            return None, None, "열 색상이 일정하지 않음"
        pixels.append(px)

    if len(pixels) < 3 or pixels[0] != ANCHOR:
        return None, None, "앵커 열을 찾지 못함"

    r, g, b = pixels[1]
    header = r * 65536 + g * 256 + b
    checksum = header & 0xFF
    size = (header >> 8) & 0xFFFF

    data = bytearray()
    for p in pixels[2:]:
        data.extend(p)
    if len(data) < size:
        return None, None, f"데이터 부족 ({len(data)} < {size})"
    data = bytes(data[:size])

    if sum(data) % 256 != checksum:
        return None, None, "체크섬 불일치"

    try:
        obj = cbor2.loads(data)
    except Exception as e:  # noqa: BLE001
        return None, None, f"CBOR 해석 실패: {e}"
    if not isinstance(obj, dict):
        return None, None, "메시지가 객체(dict)가 아님"
    obj.pop("p", None)  # Rust 원본도 이 키는 제거한다
    return obj, data, None


# ---- 이하 Windows 전용 캡처 ------------------------------------------------

def _client_region(title, max_w, max_h):
    """게임 창의 클라이언트 영역 좌상단 기준 캡처 영역. 창이 없거나 최소화면 None."""
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None
    if user32.IsIconic(hwnd):
        return None
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    rc = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    w = min(rc.right - rc.left, max_w)
    h = min(rc.bottom - rc.top, max_h)
    if w <= 0 or h <= 0:
        return None
    return {"left": pt.x, "top": pt.y, "width": w, "height": h}


def frame_to_output(obj, raw, last_raw):
    """
    디코딩된 프레임 하나를 출력할지 정한다.
    LibSerpix는 메시지(u)를 딱 한 프레임만 보여주고, 그 외 프레임은 빈 u({})를 보낸다.
    - 같은 화면이 여러 번 캡처돼도 한 번만 처리
    - 빈 프레임은 출력하지 않되 '직전 프레임'으로는 기억 (같은 메시지를 다시 보내도 출력되게)
    반환: (출력할 JSON 문자열 또는 None, 갱신된 last_raw)
    """
    if raw == last_raw:
        return None, last_raw
    u = obj.get("u")
    if not u:
        return None, raw
    return json.dumps(u, ensure_ascii=False, default=str), raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="World of Warcraft", help="게임 창 제목")
    ap.add_argument("--width", type=int, default=1240, help="캡처 너비(px)")
    ap.add_argument("--height", type=int, default=15, help="캡처 높이(px)")
    ap.add_argument("--fps", type=float, default=120, help="초당 캡처 횟수")
    ap.add_argument("--debug", action="store_true", help="실패 사유 출력")
    args = ap.parse_args()

    import mss
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 화면 배율과 무관하게 실제 픽셀 좌표 사용
    except Exception:  # noqa: BLE001
        pass

    last_raw = None
    last_note = None
    interval = 1.0 / args.fps
    MSS = getattr(mss, "MSS", None) or mss.mss  # 새 버전은 mss.MSS, 옛 버전은 mss.mss
    with MSS() as sct:
        while True:
            t0 = time.time()
            region = _client_region(args.title, args.width, args.height)
            if region is None:
                note = "게임 창을 찾지 못했거나 최소화됨"
                if args.debug and note != last_note:
                    print(note, flush=True)
                last_note = note
                time.sleep(0.5)
                continue
            shot = sct.grab(region)
            img = np.asarray(shot)[:, :, [2, 1, 0]]  # BGRA -> RGB
            obj, raw, err = decode_frame(img)
            if obj is not None:
                line, last_raw = frame_to_output(obj, raw, last_raw)
                if line:
                    print(line, flush=True)
                last_note = None
            elif args.debug and err != last_note:
                print(f"[실패] {err}", flush=True)
                last_note = err
            dt = time.time() - t0
            if dt < interval:
                time.sleep(interval - dt)


if __name__ == "__main__":
    main()