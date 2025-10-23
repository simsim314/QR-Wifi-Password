import cv2
import time
import pyperclip
from multiprocessing import Process, Queue
from pyzxing import BarCodeReader

def decode_worker(queue_in: Queue, queue_out: Queue):
    """Runs in background process to decode frames using PyZXing."""
    reader = BarCodeReader()
    while True:
        frame = queue_in.get()
        if frame is None:
            break
        try:
            results = reader.decode_array(frame)
            if results:
                for res in results:
                    data = res.get("parsed") or res.get("raw")
                    if not data:
                        continue
                    if isinstance(data, bytes):
                        data = data.decode(errors="ignore")
                    data = data.strip().replace("\n", ";")
                    parts = [p.strip() for p in data.split(";") if p.strip()]
                    if len(parts) == 4:
                        queue_out.put(parts[2])  # password
        except Exception as e:
            # Safe fallback to avoid blocking
            print(f"Decoder error: {e}")

def main(camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("❌ Could not open camera.")
        return

    queue_in, queue_out = Queue(maxsize=1), Queue()
    proc = Process(target=decode_worker, args=(queue_in, queue_out), daemon=True)
    proc.start()

    last_password = None
    print("🔍 Scanning... Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Failed to read frame.")
            break

        # Convert to RGB for PyZXing
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Send frame to decoder if queue empty
        if queue_in.empty():
            try:
                queue_in.put_nowait(rgb)
            except:
                pass

        # Check for decoded results
        while not queue_out.empty():
            password = queue_out.get_nowait()
            if password and password != last_password:
                last_password = password
                pyperclip.copy(password)
                print(f"✅ Password copied: {password}")

        cv2.imshow("PyZXing QR Scanner (Fast)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.25)

    # Cleanup
    queue_in.put(None)
    proc.join(timeout=1)
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
