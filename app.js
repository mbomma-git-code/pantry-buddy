const API_URL = "https://urneq69fyd.execute-api.us-east-2.amazonaws.com/prod/generate-meal-plan";

document.getElementById("generateBtn").addEventListener("click", generateMealPlan);

function generateMealPlan() {
  fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({})
  })
  .then(res => res.json())
  .then(data => {
    renderTable(data.week);
  })
  .catch(err => {
    console.error("Error:", err);
    alert("Failed to generate meal plan");
  });
}

function renderTable(weekData) {
  let html = `
    <table>
      <thead>
        <tr>
          <th>Day</th>
          <th>Breakfast</th>
          <th>Lunch</th>
          <th>Snack</th>
          <th>Dinner</th>
        </tr>
      </thead>
      <tbody>
  `;

  weekData.forEach(day => {
    html += `
      <tr>
        <td>${day.day}</td>
        <td>${day.breakfast}</td>
        <td>${day.lunch}</td>
        <td>${day.snack}</td>
        <td>${day.dinner}</td>
      </tr>
    `;
  });

  html += "</tbody></table>";

  document.getElementById("mealTable").innerHTML = html;
}
