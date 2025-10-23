import cv2
import pyperclip
import time

def parse_qr_to_dict(data: str) -> dict:
    """
    Parses a QR string like:
    WIFI:S:MySSID;T:WPA;P:mypassword;H:false;;
    into a dictionary: {'S': 'MySSID', 'T': 'WPA', 'P': 'mypassword', 'H': 'false'}
    """
    result = {}
    parts = data.strip(';').split(';')
    for part in parts:
        if ':' in part:
            k, v = part.split(':', 1)
            result[k] = v
    return result

def main(camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    detector = cv2.QRCodeDetector()
    last_clip = None

    print("🔍 Scanning for QR codes... Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Failed to read camera frame.")
            break

        data, points, _ = detector.detectAndDecode(frame)
        if data:
            if points is not None:
                pts = points[0].astype(int)
                for j in range(len(pts)):
                    cv2.line(frame, tuple(pts[j]), tuple(pts[(j + 1) % len(pts)]), (0, 255, 0), 2)

            qr_dict = parse_qr_to_dict(data)
            if "P" in qr_dict:
                password = qr_dict["P"]
                if password != last_clip:
                    pyperclip.copy(password)
                    last_clip = password
                    print(f"✅ Copied Wi-Fi password: {password}")
            else:
                print(f"ℹ️ No 'P' key found in QR data: {qr_dict}")

        cv2.imshow("QR Scanner", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.02)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
