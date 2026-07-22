let currentExercise = "squat";
let stateInterval = null;
let sessionActive = false;

const EXERCISE_TIPS = {
  squat: [
    { title: "Feet Position", tip: "Shoulder-width apart, toes slightly outward (5-30°)" },
    { title: "Knee Tracking", tip: "Knees must follow toes — never cave inward" },
    { title: "Depth", tip: "Hip crease below knee level = full squat" },
    { title: "Back", tip: "Keep chest up, spine neutral throughout" },
    { title: "Drive", tip: "Push through heels — not toes" },
    { title: "Breathing", tip: "Inhale down, exhale forcefully on the way up" }
  ],
  pushup: [
    { title: "Plank Base", tip: "Body must be a rigid straight line — head to heels" },
    { title: "Hand Position", tip: "Slightly wider than shoulders, directly below" },
    { title: "Elbow Angle", tip: "45° angle to torso — arrow shape, not a T" },
    { title: "Depth", tip: "Chest nearly touches floor on every rep" },
    { title: "Neck", tip: "Keep neutral — don't reach chin forward" },
    { title: "Core", tip: "Squeeze glutes and quads to stay rigid" }
  ],
  lunge: [
    { title: "Step Length", tip: "Long enough for both knees to reach 90°" },
    { title: "Front Knee", tip: "Over ankle — not past toes" },
    { title: "Torso", tip: "Stay upright — don't collapse over front thigh" },
    { title: "Balance", tip: "Feet hip-width apart — train tracks, not tightrope" },
    { title: "Back Knee", tip: "Hover 1 inch from floor at bottom" },
    { title: "Drive", tip: "Push through front heel to return" }
  ],
  bicep_curl: [
    { title: "Elbow Position", tip: "Pin elbows to sides — they must not swing" },
    { title: "Full Range", tip: "Full extension at bottom, full contraction at top" },
    { title: "Wrist", tip: "Keep wrists straight — no bending" },
    { title: "Tempo", tip: "2 seconds up, 2 seconds down — no momentum" },
    { title: "Shoulder", tip: "Shoulders stay still — only forearms move" },
    { title: "Squeeze", tip: "Squeeze bicep hard at the top of each rep" }
  ],
  shoulder_press: [
    { title: "Starting Position", tip: "Elbows at shoulder height, wrists over elbows" },
    { title: "Press Path", tip: "Push straight up — slight arc is normal" },
    { title: "Core", tip: "Brace abs — don't arch lower back" },
    { title: "Lockout", tip: "Full extension at top without shrugging" },
    { title: "Descent", tip: "Control the weight down — don't drop it" },
    { title: "Head", tip: "Chin slightly tucked, neck neutral throughout" }
  ],
  deadlift: [
    { title: "Spine", tip: "NEVER round the back — neutral spine is critical" },
    { title: "Hip Hinge", tip: "Push hips back — not a squat movement" },
    { title: "Bar Path", tip: "Bar stays close to body the entire lift" },
    { title: "Chest Up", tip: "Drive chest up as you pull — prevents rounding" },
    { title: "Foot Drive", tip: "Push the floor away — don't just pull up" },
    { title: "Lockout", tip: "Squeeze glutes at top — don't hyperextend" }
  ],
  plank: [
    { title: "Alignment", tip: "Straight line: ears, shoulders, hips, heels" },
    { title: "Hips", tip: "Neither sagging nor piking — flat and level" },
    { title: "Core", tip: "Draw navel in, brace like taking a punch" },
    { title: "Glutes", tip: "Squeeze hard — supports lower back" },
    { title: "Breathing", tip: "Slow, controlled breaths — don't hold" },
    { title: "Shoulders", tip: "Push floor away — don't sink between blades" }
  ],
  jumping_jack: [
    { title: "Arms", tip: "Full extension overhead — clap or touch at top" },
    { title: "Landing", tip: "Land softly on balls of feet — absorb impact" },
    { title: "Rhythm", tip: "Consistent pace — find your tempo and hold it" },
    { title: "Core", tip: "Keep abs lightly braced throughout" },
    { title: "Feet", tip: "Land wider than hip-width on the open phase" },
    { title: "Breathing", tip: "Natural rhythmic breathing — don't hold breath" }
  ]
};

// ── Init ──
window.onload = () => {
  setTimeout(() => {
    document.getElementById("loader").classList.add("hidden");
  }, 1500);
  renderTips("squat");
  startStatePolling();
};

// ── Exercise Selection ──
document.querySelectorAll(".ex-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ex-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentExercise = btn.dataset.ex;
    document.getElementById("exerciseBadge").textContent =
      btn.textContent.replace(/[^\w\s]/g, "").trim().toUpperCase();
    renderTips(currentExercise);
    setExercise(currentExercise);
  });
});

async function setExercise(ex) {
  try {
    await fetch("/set_exercise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exercise: ex })
    });
  } catch(e) {}
}

// ── Session Controls ──
async function startSession() {
  try {
    await fetch("/start_session", { method: "POST" });
    sessionActive = true;
    setExercise(currentExercise);
    updateFeedback("Session started! Let's go! 💪", "success");
  } catch(e) {
    updateFeedback("Cannot connect to server. Is it running?", "error");
  }
}

async function completeSet() {
  try {
    const res = await fetch("/complete_set", { method: "POST" });
    const d = await res.json();
    updateFeedback(`Set ${d.sets} complete! Rest 60 seconds then continue. 🔥`, "success");
  } catch(e) {}
}

async function resetSession() {
  try {
    await fetch("/reset", { method: "POST" });
    document.getElementById("historyList").innerHTML =
      '<div class="no-history">No sets completed yet. Start your session!</div>';
    updateFeedback("Reset! Ready to go. 💪", "info");
  } catch(e) {}
}

// ── State Polling ──
function startStatePolling() {
  stateInterval = setInterval(async () => {
    try {
      const res = await fetch("/get_state");
      const d = await res.json();
      updateUI(d);
    } catch(e) {}
  }, 500);
}

function updateUI(d) {
  document.getElementById("statReps").textContent = d.reps;
  document.getElementById("statSets").textContent = d.sets;
  document.getElementById("statCal").textContent = Math.round(d.calories);
  document.getElementById("statTime").textContent = formatTime(d.workout_time);

  const score = d.form_score;
  document.getElementById("formScoreVal").textContent = score + "%";
  const bar = document.getElementById("formBar");
  bar.style.width = score + "%";
  bar.style.background = score > 75
    ? "linear-gradient(90deg,#8db300,#c8ff00)"
    : score > 50
    ? "linear-gradient(90deg,#ff8c00,#ffb300)"
    : "linear-gradient(90deg,#cc2040,#ff3b5c)";

  if (d.feedback) updateFeedback(d.feedback, score > 75 ? "success" : "warn");

  const errWrap = document.getElementById("errorsWrap");
  if (d.errors && d.errors.length > 0) {
    errWrap.innerHTML = d.errors.map(e =>
      `<div class="error-item">⚠️ ${e}</div>`
    ).join("");
  } else {
    errWrap.innerHTML = "";
  }

  if (d.history && d.history.length > 0) {
    const list = document.getElementById("historyList");
    list.innerHTML = `
      <div class="history-header">
        <span>EXERCISE</span>
        <span>REPS</span>
        <span>FORM</span>
        <span>KCAL</span>
        <span>TIME</span>
      </div>
    ` + d.history.slice().reverse().map(h => `
      <div class="history-row">
        <span class="ex-name">${h.exercise.replace(/_/g," ").toUpperCase()}</span>
        <span>${h.reps}</span>
        <span style="color:${h.form_score>75?'#c8ff00':h.form_score>50?'#ff8c00':'#ff3b5c'}">${h.form_score}%</span>
        <span>${h.calories}</span>
        <span>${h.time}</span>
      </div>
    `).join("");
  }
}

function updateFeedback(text, type = "info") {
  const banner = document.getElementById("feedbackBanner");
  const textEl = document.getElementById("feedbackText");
  textEl.textContent = text;

  const colors = {
    success: "rgba(200,255,0,0.15)",
    error: "rgba(255,59,92,0.15)",
    warn: "rgba(255,140,0,0.15)",
    info: "rgba(0,180,255,0.1)"
  };
  const borders = {
    success: "#c8ff00",
    error: "#ff3b5c",
    warn: "#ff8c00",
    info: "#00b4ff"
  };

  banner.style.background = colors[type] || colors.info;
  banner.style.borderLeftColor = borders[type] || borders.info;
}

function renderTips(ex) {
  const tips = EXERCISE_TIPS[ex] || [];
  document.getElementById("tipsGrid").innerHTML = tips.map(t => `
    <div class="tip-card">
      <strong>${t.title}</strong>
      ${t.tip}
    </div>
  `).join("");
}

function switchMode(mode) {
  const liveView = document.getElementById("liveView");
  const uploadView = document.getElementById("uploadView");
  document.getElementById("btnLive").classList.toggle("active", mode === "live");
  document.getElementById("btnUpload").classList.toggle("active", mode === "upload");
  liveView.style.display = mode === "live" ? "block" : "none";
  uploadView.style.display = mode === "upload" ? "block" : "none";
}

function previewUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const video = document.getElementById("uploadPreview");
  const placeholder = document.getElementById("uploadPlaceholder");
  video.src = URL.createObjectURL(file);
  video.style.display = "block";
  placeholder.style.display = "none";
  switchMode("upload");
}

async function analyzeVideo() {
  const fileInput = document.getElementById("videoFile");
  if (!fileInput.files.length) {
    alert("Please select a video file first!");
    return;
  }

  const resultDiv = document.getElementById("uploadResult");
  resultDiv.style.display = "block";
  resultDiv.textContent = "Analyzing... please wait ⏳";

  const formData = new FormData();
  formData.append("video", fileInput.files[0]);
  formData.append("exercise", currentExercise);

  try {
    const res = await fetch("/analyze_upload", { method: "POST", body: formData });
    const d = await res.json();

    if (d.error) {
      resultDiv.textContent = "Error: " + d.error;
      return;
    }

    resultDiv.innerHTML = `
      <div style="color:#c8ff00;margin-bottom:6px">✅ Analysis Complete</div>
      <div>Reps detected: <b style="color:#fff">${d.reps}</b></div>
      <div>Avg form score: <b style="color:${d.avg_form_score>75?'#c8ff00':'#ff8c00'}">${d.avg_form_score}%</b></div>
      <div>Calories burned: <b style="color:#fff">${d.calories} kcal</b></div>
      <div>Frames analyzed: <b style="color:#fff">${d.frames_analyzed}</b></div>
      <div style="margin-top:8px;color:#f0f4f8">${d.feedback}</div>
    `;
  } catch(e) {
    resultDiv.textContent = "Connection error. Is the server running?";
  }
}

function formatTime(seconds) {
  if (!seconds) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}