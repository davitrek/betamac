// Grades the reply without leaving the page: the phone slides into the left
// half and the results from POST / fill the right half.
const drill = document.querySelector(".drill");
const form = drill.querySelector(".compose");
const messages = drill.querySelector(".messages");
const results = drill.querySelector(".results");
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

// Enter sends, like the old single-line input; Shift+Enter adds a newline.
textarea.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  textarea.value = "";
  resizeTextarea();

  const bubble = document.createElement("div");
  bubble.className = "message sent";
  bubble.textContent = data.get("text");
  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;

  for (const el of form.elements) el.disabled = true;
  drill.classList.add("graded");
  results.textContent = "Grading…";

  try {
    const response = await fetch(form.action, { method: "POST", body: data });
    if (!response.ok) throw new Error(response.status);
    results.innerHTML = await response.text();
  } catch (err) {
    results.textContent = "Grading failed (" + err.message + ")";
  }
});
