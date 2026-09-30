// Builds a scenario's messages as rows of (sender, text) and POSTs them, with
// the optional context box, as JSON:
// {"problem_statement": "...", "messages": [["user", "Hello"], ["contact", "Hey"], ...]}. The server
// flash()es the outcome, so a successful submit reloads the page to show it.
const form = document.querySelector(".scenario-form");
const contextBox = form.querySelector("[name=problem_statement]");
const rows = form.querySelector(".message-rows");
const rowTemplate = document.getElementById("message-row");
const addButton = form.querySelector(".add-row");
const formResponse = form.querySelector(".form-response")

// There must always be at least one row, so the only row's X is disabled.
function updateRemoveButtons() {
  const buttons = rows.querySelectorAll(".remove-row");
  for (const button of buttons) button.disabled = buttons.length === 1;
}

function updateAddButton() {
  const buttons = rows.querySelectorAll(".remove-row");
  addButton.disabled = buttons.length >= max_messages;
}

function addRow() {
  const row = rowTemplate.content.firstElementChild.cloneNode(true);
  row.querySelector(".remove-row").addEventListener("click", () => {
    row.remove();
    updateRemoveButtons();
    updateAddButton();
  });
  rows.append(row);
  updateRemoveButtons();
  updateAddButton();
  return row;
}

addButton.addEventListener("click", () => {
  addRow().querySelector("input").focus();
});

// Only fires once every text box passes the required/pattern checks.
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const messages = [...rows.querySelectorAll(".message-row")].map((row) => [
    row.querySelector("select").value,
    row.querySelector("input").value.trim(),
  ]);

  // On failure the rows are kept; any flashed error shows on the next load.
  const response = await fetch(form.action, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_statement: contextBox.value.trim(),
      messages,
    }),
  });
  if (response.ok) {
    location.reload();
  } else if (response.status == 400){
    formResponse.textContent = await response.text();
  } else {
    formResponse.textContent = "form failed to be submitted";
  }

});

addRow();
