# filename: python_code.py
# pip install opencv-python mediapipe requests
import cv2, mediapipe as mp, requests, time

# ====== AYARLAR ======
ESP32_IP = "http://172.20.10.2"
BASE = "/led"
MARGIN_INDEX, MARGIN_MIDDLE, MARGIN_RING, MARGIN_PINKY = 0.10, 0.10, 0.10, 0.13
STABLE_N, COOLDOWN = 2, 0.15
THUMB_TOGGLE_DELTA = 0.08
THUMB_INVERT = False
CAM_INDEX = 0
FRAME_W, FRAME_H = 640, 480
SHOW_DEBUG = True
# =====================

# Kamera
cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

# Mediapipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(False, 1, 0, 0.5, 0.5)
mp_draw = mp.solutions.drawing_utils

# HTTP yardimcilar
_last = 0.0
def send(path):
    global _last
    if time.time() - _last < COOLDOWN:
        return
    _last = time.time()
    try:
        requests.get(f"{ESP32_IP}{BASE}/{path}", timeout=0.6)
        print(f"[SEND] {path}")
    except Exception as e:
        print(f"[ERR] {path} -> {e}")

def all_off():
    for p in ("thumb","index","middle","ring","pinky"):
        send(f"{p}/off")

# Basparmak toggle degiskenleri
thumb_led_on = False
thumb_last_zone = "center"

def thumb_zone(handed, hl):
    tip  = hl.landmark[mp_hands.HandLandmark.THUMB_TIP]
    base = hl.landmark[mp_hands.HandLandmark.THUMB_CMC]
    s = (tip.x - base.x) if handed == "Right" else (base.x - tip.x)
    if THUMB_INVERT: s = -s
    if s > THUMB_TOGGLE_DELTA: return "right"
    elif s < -THUMB_TOGGLE_DELTA: return "left"
    else: return "center"

def fingers_open_flags(hl):
    def up(tip_id, pip_id, margin):
        return hl.landmark[tip_id].y < hl.landmark[pip_id].y - margin
    index_up  = up(mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.INDEX_FINGER_PIP, MARGIN_INDEX)
    middle_up = up(mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, MARGIN_MIDDLE)
    ring_up   = up(mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_PIP, MARGIN_RING)
    pinky_up  = up(mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.PINKY_PIP, MARGIN_PINKY)
    return [index_up, middle_up, ring_up, pinky_up]

# Baslangicta hepsi kapali
all_off()
last_cmd = {"index":None,"middle":None,"ring":None,"pinky":None}
hist_non_thumb = []

print("[INFO] Çalışıyor. ESC ile çıkış.")
while True:
    ok, frame = cap.read()
    if not ok:
        print("Kamera karesi alınamadı.")
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = hands.process(rgb)

    if res.multi_hand_landmarks:
        hl = res.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
        handed = "Right"
        if res.multi_handedness:
            handed = res.multi_handedness[0].classification[0].label

        # --- Başparmak toggle ---
        zone = thumb_zone(handed, hl)
        if zone in ("left","right") and thumb_last_zone in ("left","right") and zone != thumb_last_zone:
            thumb_led_on = not thumb_led_on
            send(f"thumb/{'on' if thumb_led_on else 'off'}")
        if zone in ("left","right"):
            thumb_last_zone = zone

        # --- Diğer parmaklar (indir = LED ON) ---
        index_up, middle_up, ring_up, pinky_up = fingers_open_flags(hl)
        desired = {
            "index":  not index_up,
            "middle": not middle_up,
            "ring":   not ring_up,
            "pinky":  not pinky_up
        }

        hist_non_thumb.append(tuple(desired[p] for p in ("index","middle","ring","pinky")))
        if len(hist_non_thumb) > STABLE_N: hist_non_thumb.pop(0)

        if len(hist_non_thumb) == STABLE_N and all(h == hist_non_thumb[0] for h in hist_non_thumb):
            for p in ("index","middle","ring","pinky"):
                cmd = f"{p}/{'on' if desired[p] else 'off'}"
                if last_cmd[p] != cmd:
                    send(cmd)
                    last_cmd[p] = cmd

        if SHOW_DEBUG:
            t1 = f"Hand:{handed}  ThumbZone:{zone}  ThumbLED:{'ON' if thumb_led_on else 'OFF'}"
            t2 = f"idx:{'ON' if desired['index'] else 'OFF'} mid:{'ON' if desired['middle'] else 'OFF'} ring:{'ON' if desired['ring'] else 'OFF'} pnk:{'ON' if desired['pinky'] else 'OFF'}"
            cv2.putText(frame, t1, (6,22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
            cv2.putText(frame, t2, (6,48), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
    else:
        hist_non_thumb.clear()

    cv2.imshow("Hand → ESP32 LEDs", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
