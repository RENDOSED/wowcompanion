"""
LibSerpix 픽셀 배치 진단 (Windows용)

게임 좌상단 캡처 영역을 PNG로 저장하고, 앵커 열의 크기와 간격, 색 구조를 출력한다.
수신기가 '앵커 열을 찾지 못함'으로 실패할 때 원인을 찾기 위한 도구.

실행:  python serpix_diag.py --title "월드 오브 워크래프트"
결과:  콘솔 출력 + serpix_capture.png 저장 (같은 폴더)
"""
import argparse
import ctypes

import numpy as np

ANCHOR = (42, 0, 69)


def rle(values):
    """연속된 같은 값을 (값, 개수)로 묶는다."""
    out = []
    for v in values:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def analyze(img):
    """img: 높이 x 너비 x 3 (RGB, uint8). 분석 결과를 콘솔에 출력."""
    h, w = img.shape[:2]
    print(f"캡처 크기: {w} x {h}")
    mask = (img[..., 0] == ANCHOR[0]) & (img[..., 1] == ANCHOR[1]) & (img[..., 2] == ANCHOR[2])
    print(f"앵커색 #2a0045 픽셀 수: {int(mask.sum())}")

    # 색이 살짝 달라졌는지 (색 보정, HDR 등) 확인용: 앵커와 비슷한 색의 수
    diff = np.abs(img.astype(int) - np.array(ANCHOR)).sum(axis=2)
    print(f"앵커와 비슷한 색(오차 합 12 이하) 픽셀 수: {int((diff <= 12).sum())}")

    flat = np.flatnonzero(mask)
    if flat.size == 0:
        print("-> 정확히 일치하는 앵커 픽셀이 없음")
        return
    y0, x0 = divmod(int(flat[0]), w)
    print(f"첫 앵커 픽셀 위치: x={x0}, y={y0}")

    # 첫 앵커 열의 세로 길이 / 가로 폭
    v = 0
    while y0 + v < h and mask[y0 + v, x0]:
        v += 1
    hw = 0
    while x0 + hw < w and mask[y0, x0 + hw]:
        hw += 1
    print(f"첫 앵커 열: 세로 연속 {v}픽셀, 가로 연속 {hw}픽셀")

    # 첫 줄(y0)에서 앵커색 구간들의 (시작 오프셋, 길이)
    row = mask[y0, x0:min(w, x0 + 400)]
    segs = []
    i = 0
    while i < len(row):
        if row[i]:
            j = i
            while j < len(row) and row[j]:
                j += 1
            segs.append((i, j - i))
            i = j
        else:
            i += 1
    print(f"첫 줄의 앵커색 구간 (오프셋, 길이) 앞 12개: {segs[:12]}")

    # 처음 몇 개 열의 세로 색 구조
    for k, (off, _ln) in enumerate(segs[:4]):
        x = x0 + off
        col = [tuple(int(c) for c in img[y, x]) for y in range(y0, min(h, y0 + 40))]
        print(f"열 {k} (x={x}) 세로 색 구조: {[(c, n) for c, n in rle(col)]}")


def _client_region(title, max_w, max_h):
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd or user32.IsIconic(hwnd):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="World of Warcraft")
    ap.add_argument("--width", type=int, default=1240)
    ap.add_argument("--height", type=int, default=15)
    ap.add_argument("--out", default="serpix_capture.png")
    args = ap.parse_args()

    import mss
    import mss.tools
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass

    region = _client_region(args.title, args.width, args.height)
    if region is None:
        print("게임 창을 찾지 못했거나 최소화됨")
        return
    print(f"캡처 영역: {region}")
    MSS = getattr(mss, "MSS", None) or mss.mss
    with MSS() as sct:
        shot = sct.grab(region)
    mss.tools.to_png(shot.rgb, shot.size, output=args.out)
    print(f"PNG 저장: {args.out}")
    img = np.asarray(shot)[:, :, [2, 1, 0]]
    analyze(img)


if __name__ == "__main__":
    main()