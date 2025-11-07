# hand_cam.py  —  Sadece el iskeleti gösterimi (ESP32 kontrolü yok)
import cv2
import mediapipe as mp

# --- Kamera ayarları (Windows'ta DSHOW genelde daha stabil) ---
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)   # 0 işe yaramazsa 1 deneyin
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)    # 320x240 istersen hız için düşürebilirsin
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# --- MediaPipe Hands (hızlı model + makul eşikler) ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,            # 0 = hızlı
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

while True:
    ok, frame = cap.read()
    if not ok:
        print("Kamera karesi alınamadı.")
        break

    # Selfie görünümü için aynala
    frame = cv2.flip(frame, 1)

    # RGB'ye çevir ve işleme
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    # El iskeletini çiz
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    # Göster
    cv2.imshow("Hand Camera (only draw)", frame)

    # q veya ESC ile çık
    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), 27):
        break

cap.release()
cv2.destroyAllWindows()
