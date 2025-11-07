# alphabet_gesture.py
# Kurulum: pip install opencv-python mediapipe requests
import cv2, mediapipe as mp, requests, time, threading

ESP32_IP = "http://172.20.10.2"  # Seri Monitörde görünen IP

# ── MediaPipe ──
mp_hands = mp.solutions.hands
hands    = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.6)
mp_draw  = mp.solutions.drawing_utils

typed = ""
current_label = "-"      # A..Z / SPACE / BKSP / CLEAR / ENTER / -
current_bits  = "-----"  # TIMRP
confirmed_gate = False   # yumruk basılıyken tekrar yazmayı engeller

ALL_FINGERS = ["thumb", "index", "middle", "ring", "pinky"]  # T I M R P sırası

# ── HTTP yardımcıları ──
def _http(path, timeout=0.6):
    try: requests.get(f"{ESP32_IP}/led/{path}", timeout=timeout)
    except: pass

def led_all_off():
    _http("all/off")

def apply_finger_leds(fingers_closed):
    """
    fingers_closed: {'thumb':0/1,'index':0/1,'middle':0/1,'ring':0/1,'pinky':0/1}
    Kapalı (1) ise LED ON, açık (0) ise OFF
    """
    for name in ALL_FINGERS:
        val = fingers_closed.get(name, 0)
        _http(f"{name}/on" if val==1 else f"{name}/off")

# ── Kamera ──
def try_open_with(backends, indices):
    for be in backends:
        for i in indices:
            cap = cv2.VideoCapture(i, be)
            if cap.isOpened():
                print(f"✅ Kamera açıldı (index={i}, backend={be})"); return cap
            cap.release()
    return None

def open_camera():
    print("📸 Kamera başlatılıyor...")
    cap = try_open_with([cv2.CAP_DSHOW, cv2.CAP_MSMF], range(0,4))
    if not cap: print("⚠️ Kamera bulunamadı. 'K' tuşuna basarak yeniden dene.")
    return cap

cap = open_camera()
def auto_retry():
    global cap
    while cap is None or not cap.isOpened():
        time.sleep(2); cap = open_camera()
        if cap and cap.isOpened(): break
if cap is None or not cap.isOpened():
    threading.Thread(target=auto_retry, daemon=True).start()

# ── Landmark yardımcıları ──
def draw_landmarks(img, lms):
    mp_draw.draw_landmarks(img, lms, mp_hands.HAND_CONNECTIONS)

def thumb_closed(lm, is_right=True):
    """
    Başparmak yatay eksenle değerlendirilir:
      Sağ el: x4 > x3 -> kapalı(1)
      Sol  el: x4 < x3 -> kapalı(1)
    """
    if is_right:  return 1 if lm[4].x > lm[3].x else 0
    else:         return 1 if lm[4].x < lm[3].x else 0

def right_hand_bits5_and_fingers(lm):
    """
    Sağ el 5 parmak: TIMRP (baş, işaret, orta, yüzük, küçük)
    1 = kapalı/bükük
    Döner: bits('TIMRP'), val(0..31), fingers_closed(dict)
    """
    T = thumb_closed(lm, is_right=True)
    I = 1 if lm[8].y  > lm[6].y  else 0
    M = 1 if lm[12].y > lm[10].y else 0
    R = 1 if lm[16].y > lm[14].y else 0
    P = 1 if lm[20].y > lm[18].y else 0
    bits = f"{T}{I}{M}{R}{P}"
    val  = (T<<4) | (I<<3) | (M<<2) | (R<<1) | P
    return bits, val, {"thumb":T, "index":I, "middle":M, "ring":R, "pinky":P}

def left_fist_code(lm):
    """
    Sol el yumruk kontrolü (TIMRP=11111 -> 31)
    Başparmak x-ekseni, diğerleri y-ekseni
    """
    T = thumb_closed(lm, is_right=False)
    I = 1 if lm[8].y  > lm[6].y  else 0
    M = 1 if lm[12].y > lm[10].y else 0
    R = 1 if lm[16].y > lm[14].y else 0
    P = 1 if lm[20].y > lm[18].y else 0
    return (T<<4)|(I<<3)|(M<<2)|(R<<1)|P

# ── Sağ el 5-bit -> Etiket (A..Z/komut) ──
def label_from_code(val):
    """
    0..25 -> A..Z
    26 -> SPACE, 27 -> BKSP, 28 -> CLEAR, 29 -> ENTER
    30,31 -> rezerve ('-')
    """
    if 0 <= val <= 25:
        return chr(ord('A') + val)
    elif val == 26:
        return "SPACE"
    elif val == 27:
        return "BKSP"
    elif val == 28:
        return "CLEAR"
    elif val == 29:
        return "ENTER"
    else:
        return "-"

print("ESC: çıkış | K: kamerayı tekrar dene")
while True:
    # Kamera hazır değilse bekle
    if cap is None or not cap.isOpened():
        key = cv2.waitKey(30) & 0xFF
        if key == 27: break
        if key == ord('k'): cap = open_camera()
        continue

    ok, frame = cap.read()
    if not ok:
        cap.release(); cap = open_camera(); continue

    frame = cv2.flip(frame, 1)
    rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res   = hands.process(rgb)

    right_bits = None; right_val = None; right_fingers = None
    left_code  = None

    if res.multi_hand_landmarks:
        for i, hl in enumerate(res.multi_hand_landmarks):
            draw_landmarks(frame, hl)
            label = res.multi_handedness[i].classification[0].label  # 'Left'/'Right'
            if label == "Right":
                right_bits, right_val, right_fingers = right_hand_bits5_and_fingers(hl.landmark)
            else:
                left_code = left_fist_code(hl.landmark)

    # ── SAĞ EL: parmak LED’leri ve mevcut etiket ──
    if right_fingers is not None:
        # Parmağı kapalı tutarsan LED sürekli yanar
        apply_finger_leds(right_fingers)
        current_bits  = right_bits
        current_label = label_from_code(right_val)

    # ── SOL EL YUMRUK (11111=31): mevcutu yaz ve YENİ HARFE GEÇ ──
    if left_code == 31 and current_label != "-" and not confirmed_gate:
        if current_label == "SPACE":
            typed += " "
        elif current_label == "BKSP":
            typed = typed[:-1] if typed else ""
        elif current_label == "CLEAR":
            typed = ""
        elif current_label == "ENTER":
            pass
        else:
            typed += current_label

        # yeni harfe geç: her şeyi sıfırla
        led_all_off()
        current_label = "-"
        current_bits  = "-----"
        confirmed_gate = True

    # Yumruk bırakılınca tekrar onaya izin ver
    if left_code != 31:
        confirmed_gate = False

    # ── Ekran ──
    cv2.putText(frame, f"Right TIMRP: {current_bits}   Current: {current_label}",
                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255,255,0), 2)
    cv2.putText(frame, f"Typed: {typed}",
                (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (0,255,0), 2)

    cv2.imshow("Right=5 fingers (TIMRP) | Left Fist=Commit & New", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == 27: break
    if key == ord('k'):
        cap.release(); cap = open_camera()

cap.release()
cv2.destroyAllWindows()
