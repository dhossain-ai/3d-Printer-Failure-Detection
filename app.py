from ultralytics import YOLO
import cv2
import tkinter as tk
from tkinter import simpledialog, messagebox

MODEL_PATH = "model.pt"
VIDEO_PATH = "demo.mp4"

fail_words = ["spaghetti", "stringing", "zits"]


def run_detection(source):
    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        messagebox.showerror("Error", f"Could not open source: {source}")
        return

    fail_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, conf=0.35, verbose=False)
        result = results[0]
        names = model.names

        fail_detected = False

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = str(names[cls_id]).lower()
                conf = float(box.conf[0])

                if any(word in label for word in fail_words) and conf >= 0.60:
                    fail_detected = True
                    break

        annotated = result.plot()

        if fail_detected:
            fail_count += 1
        else:
            fail_count = 0

        status_text = "STATUS: NORMAL"
        color = (0, 255, 0)

        if fail_count >= 3:
            status_text = "STATUS: FAIL DETECTED -> STOP PRINTER"
            color = (0, 0, 255)

        cv2.putText(
            annotated,
            status_text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            color,
            2
        )

        cv2.imshow("3D Print Failure Detection", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def use_sample_video():
    root.destroy()
    run_detection(VIDEO_PATH)


def use_webcam():
    root.destroy()
    run_detection(0)


def use_mobile_cam():
    url = simpledialog.askstring(
        "Mobile Camera URL",
        "Enter mobile camera URL:\nExample: http://192.168.1.5:4747/video"
    )
    if url:
        root.destroy()
        run_detection(url)


root = tk.Tk()
root.title("3D Print Failure Detection")
root.geometry("400x250")

label = tk.Label(root, text="Choose Input Source", font=("Arial", 16))
label.pack(pady=20)

btn1 = tk.Button(root, text="Use Sample Video", width=25, command=use_sample_video)
btn1.pack(pady=10)

btn2 = tk.Button(root, text="Use Webcam", width=25, command=use_webcam)
btn2.pack(pady=10)

btn3 = tk.Button(root, text="Use Mobile Cam URL", width=25, command=use_mobile_cam)
btn3.pack(pady=10)

root.mainloop()