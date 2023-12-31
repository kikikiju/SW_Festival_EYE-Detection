from flask import Flask, render_template, Response
import cv2
import numpy as np
from imutils import face_utils
import dlib
from keras.models import load_model
import winsound
import time

app = Flask(__name__)

IMG_SIZE = (34, 26)

detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor('shape_predictor_68_face_landmarks.dat')

model = load_model('models\\2023_11_14_23_13_17.h5')
model.summary()

def crop_eye(img, eye_points):
    x1, y1 = np.amin(eye_points, axis=0)
    x2, y2 = np.amax(eye_points, axis=0)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

    w = (x2 - x1) * 1.2
    h = w * IMG_SIZE[1] / IMG_SIZE[0]

    margin_x, margin_y = w / 2, h / 2

    min_x, min_y = int(cx - margin_x), int(cy - margin_y)
    max_x, max_y = int(cx + margin_x), int(cy + margin_y)

    eye_rect = np.rint([min_x, min_y, max_x, max_y]).astype(int)

    eye_img = img[eye_rect[1]:eye_rect[3], eye_rect[0]:eye_rect[2]]

    return eye_img, eye_rect

def play_warning_sound():
    frequency = 2500
    duration = 100
    winsound.Beep(frequency, duration)

def gen_frames():
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    start_time_no_eyes = time.time()
    start_time_eyes_closed = time.time()

    while cap.isOpened():
        ret, img_ori = cap.read()

        if not ret:
            break

        img = cv2.resize(img_ori, dsize=(0, 0), fx=0.8, fy=0.8)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = detector(gray)

        if len(faces) == 0:
            elapsed_time_no_eyes = time.time() - start_time_no_eyes
            if elapsed_time_no_eyes >= 3:
                play_warning_sound()
                start_time_eyes_closed = time.time()
                # Display "Warning" on the camera feed
                font_scale = 5
                font_thickness = 7
                font_color = (0, 0, 255)  # Red color
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = 'Warning'
                text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
                text_x = (img.shape[1] - text_size[0]) // 2
                text_y = (img.shape[0] + text_size[1]) // 2
                cv2.putText(img, text, (text_x, text_y), font, font_scale, font_color, font_thickness)
        else:
            start_time_no_eyes = time.time()

            for face in faces:
                shapes = predictor(gray, face)
                shapes = face_utils.shape_to_np(shapes)

                eye_img_l, eye_rect_l = crop_eye(gray, eye_points=shapes[36:42])
                eye_img_r, eye_rect_r = crop_eye(gray, eye_points=shapes[42:48])

                eye_img_l = cv2.resize(eye_img_l, dsize=IMG_SIZE)
                eye_img_r = cv2.resize(eye_img_r, dsize=IMG_SIZE)
                eye_img_r = cv2.flip(eye_img_r, flipCode=1)

                eye_input_l = eye_img_l.copy().reshape((1, IMG_SIZE[1], IMG_SIZE[0], 1)).astype(np.float32) / 255.
                eye_input_r = eye_img_r.copy().reshape((1, IMG_SIZE[1], IMG_SIZE[0], 1)).astype(np.float32) / 255.

                pred_l = model.predict(eye_input_l)[0, 0]
                pred_r = model.predict(eye_input_r)[0, 0]

                # Visualize
                state_l = 'Open' if pred_l > 0.5 else 'Close'
                state_r = 'Open' if pred_r > 0.5 else 'Close'

                cv2.rectangle(img, pt1=tuple(eye_rect_l[0:2]), pt2=tuple(eye_rect_l[2:4]), color=(255, 255, 255), thickness=2)
                cv2.rectangle(img, pt1=tuple(eye_rect_r[0:2]), pt2=tuple(eye_rect_r[2:4]), color=(255, 255, 255), thickness=2)

                # Display accuracy as a number
                cv2.putText(img, f'Left Eye: {pred_l:.2f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(img, f'Right Eye: {pred_r:.2f}', (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                # Check for warning condition and play warning sound
                if pred_l <= 0.1 and pred_r <= 0.1:
                    elapsed_time_eyes_closed = time.time() - start_time_eyes_closed
                    if elapsed_time_eyes_closed >= 3:
                        play_warning_sound()
                        # Display "Warning" on the camera feed
                        font_scale = 5
                        font_thickness = 7
                        font_color = (0, 0, 255)  # Red color
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        text = 'Warning'
                        text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
                        text_x = (img.shape[1] - text_size[0]) // 2
                        text_y = (img.shape[0] + text_size[1]) // 2
                        cv2.putText(img, text, (text_x, text_y), font, font_scale, font_color, font_thickness)

        _, jpeg = cv2.imencode('.jpg', img)
        frame = jpeg.tobytes()
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

    cap.release()
    cv2.destroyAllWindows()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)
