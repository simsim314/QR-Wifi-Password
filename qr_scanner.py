import cv2
import time
import pyperclip
import numpy as np
from multiprocessing import Process, Queue

import zxingcpp   # zxing-cpp bindings (C++ backend)


def _position_to_primitives(pos):
    """
    Convert zxingcpp.Position or similar objects into a plain list of (x, y) tuples.
    Handles Position with attributes top_left/top_right/bottom_right/bottom_left,
    iterable-like positions, numpy-like positions, and tuple/list points.
    Returns [] if conversion fails or pos is None.
    """
    if pos is None:
        return []

    # 1) If it's a Position-like struct with named corners, read them
    try:
        if hasattr(pos, "top_left") and hasattr(pos, "top_right") and \
           hasattr(pos, "bottom_right") and hasattr(pos, "bottom_left"):
            pts = []
            for corner_name in ("top_left", "top_right", "bottom_right", "bottom_left"):
                corner = getattr(pos, corner_name)
                # corner may be object with x/y or tuple/list
                try:
                    if hasattr(corner, "x") and hasattr(corner, "y"):
                        x = float(getattr(corner, "x"))
                        y = float(getattr(corner, "y"))
                    else:
                        # sequence fallback
                        x = float(corner[0])
                        y = float(corner[1])
                    pts.append((x, y))
                except Exception:
                    # if any corner fails, abandon this path
                    pts = []
                    break
            if len(pts) == 4:
                return pts
    except Exception:
        pass

    # 2) Try numpy-friendly conversion (pos could be array-like)
    try:
        arr = np.array(pos, dtype=float)
        if arr.size and arr.ndim >= 2 and arr.shape[-1] >= 2:
            arr2 = arr.reshape((-1, 2))
            return [(float(x), float(y)) for x, y in arr2]
    except Exception:
        pass

    # 3) Try to iterate over pos and read per-element x/y or [0],[1]
    out = []
    try:
        for p in pos:
            x = y = None
            # attribute access
            try:
                if hasattr(p, "x"):
                    x = float(getattr(p, "x"))
                if hasattr(p, "y"):
                    y = float(getattr(p, "y"))
            except Exception:
                pass
            # sequence access fallback
            if x is None or y is None:
                try:
                    x = float(p[0]) if x is None else x
                except Exception:
                    pass
                try:
                    y = float(p[1]) if y is None else y
                except Exception:
                    pass
            if x is not None and y is not None:
                out.append((x, y))
    except Exception:
        pass

    return out


def decode_worker(queue_in: Queue, queue_out: Queue):
    """Background QR decoder using zxing-cpp. Converts positions to plain tuples before sending."""
    while True:
        frame = queue_in.get()
        if frame is None:
            break
        try:
            results = zxingcpp.read_barcodes(frame)
            if not results:
                continue

            for res in results:
                data = getattr(res, "text", None) or getattr(res, "raw", None)
                if not data:
                    continue

                if isinstance(data, bytes):
                    data = data.decode(errors="ignore")

                data = data.strip().replace("\n", ";")
                parts = [p.strip() for p in data.split(";") if p.strip()]
                if len(parts) == 4:
                    # --- CLEAN password here ---
                    raw_pw = parts[2]
                    if isinstance(raw_pw, str) and raw_pw.lower().startswith("p:"):
                        password = raw_pw.split(":", 1)[1].strip()
                    else:
                        password = raw_pw.strip()

                    # convert position to simple list of (x,y) tuples
                    pos = getattr(res, "position", None)
                    points = _position_to_primitives(pos)

                    # send only picklable primitives
                    queue_out.put({
                        "password": password,
                        "points": points
                    })
        except Exception as e:
            # keep the worker alive on errors and print a short message
            print(f"Decoder error: {e}")


def crop_with_border(frame, points, border=20, size=500):
    """Crop QR area using min/max of points, add border, resize to `size`."""
    if not points or len(points) < 1:
        return None

    try:
        pts = np.array(points, dtype=np.float32)
        if pts.ndim != 2 or pts.shape[1] < 2:
            return None
    except Exception:
        return None

    h, w = frame.shape[:2]
    x_min = int(max(np.min(pts[:, 0]) - border, 0))
    y_min = int(max(np.min(pts[:, 1]) - border, 0))
    x_max = int(min(np.max(pts[:, 0]) + border, w))
    y_max = int(min(np.max(pts[:, 1]) + border, h))

    if x_max <= x_min or y_max <= y_min:
        return None

    crop = frame[y_min:y_max, x_min:x_max]
    if crop.size == 0:
        return None
    crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_CUBIC)
    return crop


def main(camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("❌ Could not open camera.")
        return

    queue_in, queue_out = Queue(maxsize=1), Queue()
    proc = Process(target=decode_worker, args=(queue_in, queue_out), daemon=True)
    proc.start()

    last_password = None
    qr_found = False
    detected_frame = None
    qr_image = None

    print("🔍 Scanning... Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Failed to read frame.")
            break

        # send frame to worker (BGR numpy array)
        if not qr_found and queue_in.empty():
            try:
                queue_in.put_nowait(frame.copy())
            except Exception:
                pass

        # handle decoded results (points are plain tuples now)
        while not queue_out.empty():
            result = queue_out.get_nowait()
            password = result.get("password")
            points = result.get("points", [])
            if password and password != last_password:
                last_password = password
                pyperclip.copy(password)
                print(f"✅ Copied Wi-Fi password: {password}")

                detected_frame = frame.copy()
                qr_image = crop_with_border(detected_frame, points)
                qr_found = True
                # print points for visibility
                #if points:
                #    print("Detected points:", [(int(round(x)), int(round(y))) for x, y in points])
                #else:
                #    print("No points detected")
                #print("✅ Detected QR")
                break

        if qr_found:
            cap.release()
            cv2.destroyAllWindows()
            if qr_image is not None:
                cv2.imshow("Detected QR", qr_image)
            else:
                # show detection frame with polylines if possible
                if points and len(points) >= 2:
                    try:
                        pts = np.array(points, dtype=np.int32).reshape(-1, 2)
                        cv2.polylines(detected_frame, [pts.reshape((-1, 1, 2))], True, (0, 255, 0), 3)
                    except Exception:
                        pass
                cv2.imshow("Detected QR Frame", detected_frame)
            cv2.waitKey(0)
            break

        cv2.imshow("QR Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.05)

    queue_in.put(None)
    proc.join(timeout=1)
    try:
        cap.release()
    except Exception:
        pass
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
