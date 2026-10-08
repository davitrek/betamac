// The send button (or Enter) only adds a bubble to the phone. Submit posts
// every sent message to POST /grade, and the results fade in below the
// context box, to the right of the phone.
const drill = document.querySelector(".drill");
const form = drill.querySelector(".compose");
const messages = drill.querySelector(".messages");
const results = drill.querySelector(".results-body");
const submitButton = drill.querySelector(".submit-reply");
const nextButton = drill.querySelector(".next-scenario");
const textarea = form.elements.text;

// Fit the textarea to its content (CSS caps it at 3 lines). The messages pane
// shrinks to make room, so keep it scrolled to the bottom if it was there.
function resizeTextarea() {
  const atBottom =
    messages.scrollHeight - messages.scrollTop - messages.clientHeight < 1;
  textarea.style.height = "auto";
  textarea.style.height = textarea.scrollHeight + "px";
  if (atBottom) messages.scrollTop = messages.scrollHeight;
}

textarea.addEventListener("input", resizeTextarea);

// Enter sends, Shift+Enter adds a newline.
textarea.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

// the user's messages, in the order they were sent
const sentMessages = [];

// The server allows one grading per 5 seconds, so Submit stays disabled for
// that long after the last one. The time is kept in localStorage because
// Next scenario reloads the page.
const COOLDOWN_MS = 5000;
const WAIT_TOOLTIP = "Please wait before submitting again";
let coolingDown = false;
let cooldownTimer;

function readLastGraded() {
  try {
    return Number(localStorage.getItem("lastGradedAt")) || 0;
  } catch {
    return 0;
  }
}

function startCooldown(ms) {
  coolingDown = true;
  submitButton.disabled = true;
  submitButton.title = WAIT_TOOLTIP;
  clearTimeout(cooldownTimer);
  cooldownTimer = setTimeout(() => {
    coolingDown = false;
    submitButton.title = "";
    submitButton.disabled = sentMessages.length === 0;
  }, ms);
}

const sinceLastGraded = Date.now() - readLastGraded();
if (sinceLastGraded < COOLDOWN_MS) startCooldown(COOLDOWN_MS - sinceLastGraded);

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = textarea.value;
  textarea.value = "";
  resizeTextarea();
  if (!text.trim()) return;

  const bubble = document.createElement("div");
  bubble.className = "message sent";
  bubble.textContent = text;
  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;

  sentMessages.push(text);
  if (!coolingDown) submitButton.disabled = false;
});

submitButton.addEventListener("click", async () => {
  submitButton.hidden = true;
  for (const el of form.elements) el.disabled = true;
  drill.classList.add("graded");
  results.textContent = "Grading…";

  try {
    const response = await fetch(submitButton.dataset.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario_id: submitButton.dataset.scenarioId,
        messages: sentMessages,
      }),
    });
    if (response.status === 429) {
      // rate limited: show the server's message and let them retry
      results.textContent = await response.text();
      submitButton.hidden = false;
      for (const el of form.elements) el.disabled = false;
      startCooldown(COOLDOWN_MS);
      return;
    }
    if (!response.ok) throw new Error(response.status);
    results.innerHTML = await response.text();
    try {
      localStorage.setItem("lastGradedAt", String(Date.now()));
    } catch {}
  } catch (err) {
    results.textContent = "Grading failed (" + err.message + ")";
  }
  nextButton.hidden = false;
});

// GET / picks a new random scenario.
nextButton.addEventListener("click", () => location.reload());

// Only rendered once the user has completed every scenario.
document.querySelector("dialog.all-seen")?.showModal();
