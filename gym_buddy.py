"""
GymBuddy Pro — Advanced AI Fitness Coach
Flask backend with OpenCV + MediaPipe pose detection
Supports: Webcam live + Video upload
Exercises: Squat, Push-up, Lunge, Bicep Curl, Shoulder Press,
           Deadlift, Plank, Pull-up, Tricep Dip, Jumping Jack
"""

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import base64
import json
import time
import os
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ── MediaPipe Setup ──
mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
mp_style = mp.solutions.drawing_styles

# ── Global State ──
state = {
    "exercise": "squat",
    "reps": 0,
    "sets": 0,
    "phase": "up",
    "feedback": "Ready! Start your workout.",
    "form_score": 100,
    "calories": 0.0,
    "workout_time": 0,
    "session_start": None,
    "errors": [],
    "history": []
}

camera = None

# ══════════════════════════════════════
# ANGLE CALCULATION
# ══════════════════════════════════════
def calc_angle(a, b, c):
    """Calculate angle at joint b between points a-b-c"""
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba = a - b
    bc = c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

def get_coords(landmarks, idx):
    lm = landmarks[idx]
    return [lm.x, lm.y]

def visibility_ok(landmarks, indices, threshold=0.5):
    return all(landmarks[i].visibility > threshold for i in indices)

# ══════════════════════════════════════
# EXERCISE ANALYZERS
# ══════════════════════════════════════

def analyze_squat(lm, state):
    needed = [23, 25, 27, 24, 26, 28, 11, 12]
    if not visibility_ok(lm, needed): return

    # Angles
    l_hip, l_knee, l_ankle = get_coords(lm, 23), get_coords(lm, 25), get_coords(lm, 27)
    r_hip, r_knee, r_ankle = get_coords(lm, 24), get_coords(lm, 26), get_coords(lm, 28)
    l_shoulder = get_coords(lm, 11)
    r_shoulder = get_coords(lm, 12)

    l_knee_angle = calc_angle(l_hip, l_knee, l_ankle)
    r_knee_angle = calc_angle(r_hip, r_knee, r_ankle)
    knee_angle = (l_knee_angle + r_knee_angle) / 2

    # Torso lean
    mid_hip = [(l_hip[0]+r_hip[0])/2, (l_hip[1]+r_hip[1])/2]
    mid_shoulder = [(l_shoulder[0]+r_shoulder[0])/2, (l_shoulder[1]+r_shoulder[1])/2]
    torso_angle = calc_angle([mid_shoulder[0], 0], mid_shoulder, mid_hip)

    errors = []
    score = 100

    # Knee valgus check
    if abs(l_knee[0] - l_ankle[0]) > 0.05:
        errors.append("Left knee caving in — push knee out!")
        score -= 15
    if abs(r_knee[0] - r_ankle[0]) > 0.05:
        errors.append("Right knee caving in — push knee out!")
        score -= 15

    # Depth check
    if state["phase"] == "down" and knee_angle > 100:
        errors.append("Go deeper! Hit parallel (thighs parallel to floor)")
        score -= 20

    # Forward lean
    if torso_angle < 60:
        errors.append("Chest up! Too much forward lean")
        score -= 15

    # Rep counting
    if knee_angle < 100:
        state["phase"] = "down"
    elif knee_angle > 160 and state["phase"] == "down":
        state["phase"] = "up"
        state["reps"] += 1
        state["calories"] += 0.32
        feedback = f"Rep {state['reps']}! " + ("Great depth! 🔥" if score > 80 else "Work on form!")
        state["feedback"] = feedback

    if errors:
        state["errors"] = errors
        state["feedback"] = errors[0]

    state["form_score"] = max(0, score)


def analyze_pushup(lm, state):
    needed = [11, 13, 15, 12, 14, 16, 23, 24]
    if not visibility_ok(lm, needed): return

    l_shoulder, l_elbow, l_wrist = get_coords(lm, 11), get_coords(lm, 13), get_coords(lm, 15)
    r_shoulder, r_elbow, r_wrist = get_coords(lm, 12), get_coords(lm, 14), get_coords(lm, 16)
    l_hip, r_hip = get_coords(lm, 23), get_coords(lm, 24)

    l_elbow_angle = calc_angle(l_shoulder, l_elbow, l_wrist)
    r_elbow_angle = calc_angle(r_shoulder, r_elbow, r_wrist)
    elbow_angle = (l_elbow_angle + r_elbow_angle) / 2

    # Body alignment
    mid_shoulder = [(l_shoulder[0]+r_shoulder[0])/2, (l_shoulder[1]+r_shoulder[1])/2]
    mid_hip = [(l_hip[0]+r_hip[0])/2, (l_hip[1]+r_hip[1])/2]
    body_angle = calc_angle([mid_shoulder[0], 0], mid_shoulder, mid_hip)

    errors = []
    score = 100

    # Sagging hips
    if mid_hip[1] > mid_shoulder[1] + 0.05:
        errors.append("Hips sagging! Squeeze glutes and core!")
        score -= 25

    # Piking hips
    if mid_hip[1] < mid_shoulder[1] - 0.08:
        errors.append("Hips too high! Lower them to plank position")
        score -= 20

    # Elbow flare check
    if abs(l_elbow[0] - l_shoulder[0]) > 0.15:
        errors.append("Elbows flaring out — tuck 45 degrees!")
        score -= 15

    # Depth
    if state["phase"] == "down" and elbow_angle > 70:
        errors.append("Go lower! Chest should nearly touch floor")
        score -= 20

    # Rep counting
    if elbow_angle < 70:
        state["phase"] = "down"
    elif elbow_angle > 150 and state["phase"] == "down":
        state["phase"] = "up"
        state["reps"] += 1
        state["calories"] += 0.29
        state["feedback"] = f"Rep {state['reps']}! " + ("Explosive push! 💪" if score > 80 else "Control the movement!")

    if errors:
        state["errors"] = errors[:1]
        state["feedback"] = errors[0]

    state["form_score"] = max(0, score)


def analyze_lunge(lm, state):
    needed = [23, 25, 27, 24, 26, 28]
    if not visibility_ok(lm, needed): return

    l_hip, l_knee, l_ankle = get_coords(lm, 23), get_coords(lm, 25), get_coords(lm, 27)
    r_hip, r_knee, r_ankle = get_coords(lm, 24), get_coords(lm, 26), get_coords(lm, 28)

    l_knee_angle = calc_angle(l_hip, l_knee, l_ankle)
    r_knee_angle = calc_angle(r_hip, r_knee, r_ankle)
    front_knee_angle = min(l_knee_angle, r_knee_angle)

    errors = []
    score = 100

    # Knee over toe
    front_knee = l_knee if l_knee_angle < r_knee_angle else r_knee
    front_ankle = l_ankle if l_knee_angle < r_knee_angle else r_ankle
    if front_knee[0] - front_ankle[0] > 0.08:
        errors.append("Front knee past toes — step longer!")
        score -= 20

    # Knee valgus
    if abs(l_knee[0] - l_ankle[0]) > 0.06:
        errors.append("Left knee collapsing — engage glutes!")
        score -= 15

    # Depth
    if state["phase"] == "down" and front_knee_angle > 110:
        errors.append("Lunge deeper — aim for 90 degrees!")
        score -= 15

    # Rep counting
    if front_knee_angle < 110:
        state["phase"] = "down"
    elif front_knee_angle > 160 and state["phase"] == "down":
        state["phase"] = "up"
        state["reps"] += 1
        state["calories"] += 0.28
        state["feedback"] = f"Rep {state['reps']}! " + ("Solid lunge! 🦵" if score > 80 else "Focus on alignment!")

    if errors:
        state["errors"] = errors[:1]
        state["feedback"] = errors[0]

    state["form_score"] = max(0, score)


def analyze_bicep_curl(lm, state):
    needed = [11, 13, 15, 12, 14, 16]
    if not visibility_ok(lm, needed, 0.4): return

    l_shoulder, l_elbow, l_wrist = get_coords(lm, 11), get_coords(lm, 13), get_coords(lm, 15)
    r_shoulder, r_elbow, r_wrist = get_coords(lm, 12), get_coords(lm, 14), get_coords(lm, 16)

    l_angle = calc_angle(l_shoulder, l_elbow, l_wrist)
    r_angle = calc_angle(r_shoulder, r_elbow, r_wrist)
    avg_angle = (l_angle + r_angle) / 2

    errors = []
    score = 100

    # Elbow swinging
    if abs(l_elbow[0] - l_shoulder[0]) > 0.12:
        errors.append("Keep elbows pinned to sides!")
        score -= 20
    if abs(r_elbow[0] - r_shoulder[0]) > 0.12:
        errors.append("Right elbow drifting — control it!")
        score -= 20

    # Full extension
    if state["phase"] == "down" and avg_angle < 150:
        errors.append("Fully extend arms at bottom!")
        score -= 15

    # Rep count
    if avg_angle < 50:
        state["phase"] = "up"
    elif avg_angle > 150 and state["phase"] == "up":
        state["phase"] = "down"
        state["reps"] += 1
        state["calories"] += 0.15
        state["feedback"] = f"Rep {state['reps']}! " + ("Perfect curl! 💪" if score > 80 else "Slow it down!")

    if errors:
        state["errors"] = errors[:1]
        state["feedback"] = errors[0]

    state["form_score"] = max(0, score)


def analyze_shoulder_press(lm, state):
    needed = [11, 13, 15, 12, 14, 16]
    if not visibility_ok(lm, needed, 0.4): return

    l_shoulder, l_elbow, l_wrist = get_coords(lm, 11), get_coords(lm, 13), get_coords(lm, 15)
    r_shoulder, r_elbow, r_wrist = get_coords(lm, 12), get_coords(lm, 14), get_coords(lm, 16)

    l_angle = calc_angle(l_shoulder, l_elbow, l_wrist)
    r_angle = calc_angle(r_shoulder, r_elbow, r_wrist)
    avg_angle = (l_angle + r_angle) / 2

    errors = []
    score = 100

    # Wrist alignment
    if abs(l_wrist[0] - l_elbow[0]) > 0.1:
        errors.append("Keep wrists straight over elbows!")
        score -= 15

    # Elbow position
    if l_elbow[1] < l_shoulder[1] - 0.05:
        errors.append("Lower elbows to shoulder height at bottom")
        score -= 15

    # Rep count
    if avg_angle > 160:
        state["phase"] = "up"
    elif avg_angle < 90 and state["phase"] == "up":
        state["phase"] = "down"
        state["reps"] += 1
        state["calories"] += 0.22
        state["feedback"] = f"Rep {state['reps']}! " + ("Powerful press! 🏋️" if score > 80 else "Control descent!")

    if errors:
        state["errors"] = errors[:1]
        state["feedback"] = errors[0]

    state["form_score"] = max(0, score)


def analyze_plank(lm, state):
    needed = [11, 12, 23, 24, 25, 26]
    if not visibility_ok(lm, needed): return

    l_shoulder = get_coords(lm, 11)
    r_shoulder = get_coords(lm, 12)
    l_hip = get_coords(lm, 23)
    r_hip = get_coords(lm, 24)
    l_knee = get_coords(lm, 25)
    r_knee = get_coords(lm, 26)

    mid_shoulder = [(l_shoulder[0]+r_shoulder[0])/2, (l_shoulder[1]+r_shoulder[1])/2]
    mid_hip = [(l_hip[0]+r_hip[0])/2, (l_hip[1]+r_hip[1])/2]
    mid_knee = [(l_knee[0]+r_knee[0])/2, (l_knee[1]+r_knee[1])/2]

    body_angle = calc_angle(mid_shoulder, mid_hip, mid_knee)

    errors = []
    score = 100

    if mid_hip[1] > mid_shoulder[1] + 0.06:
        errors.append("Hips sagging! Squeeze core and glutes!")
        score -= 30
    elif mid_hip[1] < mid_shoulder[1] - 0.08:
        errors.append("Hips too high! Lower to straight line")
        score -= 25

    if body_angle < 160:
        errors.append("Straighten your body — head to heels!")
        score -= 20

    # Plank timer
    if not state.get("plank_start"):
        state["plank_start"] = time.time()

    elapsed = int(time.time() - state.get("plank_start", time.time()))
    state["feedback"] = f"Plank: {elapsed}s — {'Great form! 🔥' if score > 80 else 'Fix your form!'}"
    state["reps"] = elapsed  # show seconds as reps

    if errors:
        state["errors"] = errors[:1]
        state["feedback"] = errors[0] + f" ({elapsed}s)"

    state["form_score"] = max(0, score)
    state["calories"] += 0.008


def analyze_deadlift(lm, state):
    needed = [11, 12, 23, 24, 25, 26]
    if not visibility_ok(lm, needed): return

    l_shoulder = get_coords(lm, 11)
    r_shoulder = get_coords(lm, 12)
    l_hip = get_coords(lm, 23)
    r_hip = get_coords(lm, 24)
    l_knee = get_coords(lm, 25)
    r_knee = get_coords(lm, 26)

    mid_shoulder = [(l_shoulder[0]+r_shoulder[0])/2, (l_shoulder[1]+r_shoulder[1])/2]
    mid_hip = [(l_hip[0]+r_hip[0])/2, (l_hip[1]+r_hip[1])/2]
    mid_knee = [(l_knee[0]+r_knee[0])/2, (l_knee[1]+r_knee[1])/2]

    hip_angle = calc_angle(mid_shoulder, mid_hip, mid_knee)

    errors = []
    score = 100

    # Back rounding
    if mid_shoulder[1] - mid_hip[1] > 0.05:
        errors.append("Keep chest up — back is rounding!")
        score -= 30

    # Bar path (shoulder over foot)
    if abs(l_shoulder[0] - get_coords(lm, 27)[0]) > 0.15:
        errors.append("Bar drifting — keep it close to body!")
        score -= 20

    # Rep count
    if hip_angle < 90:
        state["phase"] = "down"
    elif hip_angle > 160 and state["phase"] == "down":
        state["phase"] = "up"
        state["reps"] += 1
        state["calories"] += 0.45
        state["feedback"] = f"Rep {state['reps']}! " + ("Powerful pull! 💪" if score > 80 else "Protect your back!")

    if errors:
        state["errors"] = errors[:1]
        state["feedback"] = errors[0]

    state["form_score"] = max(0, score)


def analyze_jumping_jack(lm, state):
    needed = [15, 16, 27, 28]
    if not visibility_ok(lm, needed, 0.4): return

    l_wrist = get_coords(lm, 15)
    r_wrist = get_coords(lm, 16)
    l_ankle = get_coords(lm, 27)
    r_ankle = get_coords(lm, 28)

    arm_spread = abs(l_wrist[0] - r_wrist[0])
    leg_spread = abs(l_ankle[0] - r_ankle[0])

    if arm_spread > 0.6 and leg_spread > 0.3:
        if state["phase"] == "closed":
            state["phase"] = "open"
    elif arm_spread < 0.3 and leg_spread < 0.15:
        if state["phase"] == "open":
            state["phase"] = "closed"
            state["reps"] += 1
            state["calories"] += 0.1
            state["feedback"] = f"Rep {state['reps']}! Keep the rhythm! ⚡"

    state["form_score"] = 95
    if state["phase"] == "closed":
        state["feedback"] = "Jump! Spread arms and legs!"


# ── Exercise Router ──
EXERCISE_MAP = {
    "squat":         analyze_squat,
    "pushup":        analyze_pushup,
    "lunge":         analyze_lunge,
    "bicep_curl":    analyze_bicep_curl,
    "shoulder_press":analyze_shoulder_press,
    "plank":         analyze_plank,
    "deadlift":      analyze_deadlift,
    "jumping_jack":  analyze_jumping_jack,
}

EXERCISE_CALORIES = {
    "squat": 0.32, "pushup": 0.29, "lunge": 0.28,
    "bicep_curl": 0.15, "shoulder_press": 0.22,
    "plank": 0.008, "deadlift": 0.45, "jumping_jack": 0.1
}


# ══════════════════════════════════════
# FRAME PROCESSOR
# ══════════════════════════════════════
def process_frame(frame, pose_model):
    global state

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose_model.process(rgb)

    # Draw skeleton
    if result.pose_landmarks:
        mp_draw.draw_landmarks(
            frame,
            result.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_draw.DrawingSpec(color=(0, 255, 128), thickness=2, circle_radius=3),
            connection_drawing_spec=mp_draw.DrawingSpec(color=(0, 200, 255), thickness=2)
        )

        lm = result.pose_landmarks.landmark
        ex = state["exercise"]
        if ex in EXERCISE_MAP:
            try:
                EXERCISE_MAP[ex](lm, state)
            except Exception as e:
                pass

    # Overlay UI on frame
    h, w = frame.shape[:2]

    # Form score bar
    score = state["form_score"]
    bar_color = (0, 255, 128) if score > 75 else (0, 165, 255) if score > 50 else (0, 0, 255)
    cv2.rectangle(frame, (10, h-50), (10 + int((w-20) * score/100), h-30), bar_color, -1)
    cv2.rectangle(frame, (10, h-50), (w-10, h-30), (50,50,50), 2)
    cv2.putText(frame, f"FORM: {score}%", (12, h-55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

    # Reps counter
    cv2.putText(frame, f"REPS: {state['reps']}", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,128), 3)

    # Feedback text
    feedback = state["feedback"][:60]
    cv2.putText(frame, feedback, (10, h-65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,100), 1)

    return frame


# ══════════════════════════════════════
# WEBCAM STREAM
# ══════════════════════════════════════
def gen_frames():
    global camera
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    with mp_pose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6) as pose:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            frame = process_frame(frame, pose)
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')


# ══════════════════════════════════════
# ROUTES
# ══════════════════════════════════════
@app.route("/")
def home():
    return send_from_directory('.', 'index.html')

@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/set_exercise", methods=["POST"])
def set_exercise():
    global state
    data = request.json
    ex = data.get("exercise", "squat")
    state["exercise"] = ex
    state["reps"] = 0
    state["phase"] = "up"
    state["errors"] = []
    state["form_score"] = 100
    state["plank_start"] = None
    state["feedback"] = f"Starting {ex.replace('_',' ').title()}! Get into position."
    return jsonify({"ok": True, "exercise": ex})

@app.route("/complete_set", methods=["POST"])
def complete_set():
    global state
    state["sets"] += 1
    state["history"].append({
        "exercise": state["exercise"],
        "reps": state["reps"],
        "form_score": state["form_score"],
        "calories": round(state["calories"], 1),
        "time": datetime.now().strftime("%H:%M:%S")
    })
    state["reps"] = 0
    state["phase"] = "up"
    state["errors"] = []
    state["feedback"] = f"Set {state['sets']} done! Rest 60 seconds."
    return jsonify({"ok": True, "sets": state["sets"]})

@app.route("/get_state")
def get_state():
    if state["session_start"]:
        state["workout_time"] = int(time.time() - state["session_start"])
    return jsonify(state)

@app.route("/start_session", methods=["POST"])
def start_session():
    global state
    state["session_start"] = time.time()
    state["reps"] = 0
    state["sets"] = 0
    state["calories"] = 0.0
    state["history"] = []
    state["feedback"] = "Session started! Let's go! 💪"
    return jsonify({"ok": True})

@app.route("/reset", methods=["POST"])
def reset():
    global state
    state.update({"reps": 0, "sets": 0, "phase": "up",
                  "feedback": "Reset! Ready to go.", "form_score": 100,
                  "calories": 0.0, "errors": [], "history": [],
                  "session_start": None, "workout_time": 0, "plank_start": None})
    return jsonify({"ok": True})

@app.route("/analyze_upload", methods=["POST"])
def analyze_upload():
    """Analyze uploaded video file"""
    if "video" not in request.files:
        return jsonify({"error": "No video uploaded"})

    file = request.files["video"]
    tmp_path = "tmp_upload.mp4"
    file.save(tmp_path)

    exercise = request.form.get("exercise", "squat")
    local_state = {
        "exercise": exercise, "reps": 0, "sets": 0,
        "phase": "up", "feedback": "", "form_score": 100,
        "calories": 0.0, "errors": [], "plank_start": None
    }

    cap = cv2.VideoCapture(tmp_path)
    frames_analyzed = 0
    score_sum = 0

    with mp_pose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            if result.pose_landmarks:
                lm = result.pose_landmarks.landmark
                if exercise in EXERCISE_MAP:
                    try:
                        EXERCISE_MAP[exercise](lm, local_state)
                    except:
                        pass
                score_sum += local_state["form_score"]
                frames_analyzed += 1
            cap.release() if frames_analyzed > 300 else None

    cap.release()
    os.remove(tmp_path)

    avg_score = score_sum / max(frames_analyzed, 1)
    return jsonify({
        "reps": local_state["reps"],
        "avg_form_score": round(avg_score, 1),
        "calories": round(local_state["calories"], 1),
        "feedback": local_state["feedback"],
        "frames_analyzed": frames_analyzed
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  GymBuddy Pro — AI Fitness Coach")
    print("  Running at: http://localhost:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)