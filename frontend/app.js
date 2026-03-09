// Load configuration
const API_URL = `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.v2.generateMealPlan}`;

function debugLog(runId, hypothesisId, location, message, data) {
  fetch('http://127.0.0.1:7242/ingest/a9275978-a813-4db2-a98a-49f2877ecb79',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'2f1a8e'},body:JSON.stringify({sessionId:'2f1a8e',runId,hypothesisId,location,message,data,timestamp:Date.now()})}).catch(()=>{});
}

document.getElementById("generateBtn").addEventListener("click", generateMealPlan);

function generateMealPlan() {
  // #region agent log
  debugLog('pre-fix', 'H1', 'frontend/app.js:11', 'Generate meal plan requested', {
    apiUrl: API_URL,
    apiVersion: CONFIG.API_VERSION,
    baseUrl: CONFIG.API_BASE_URL
  });
  // #endregion
  fetch(API_URL, {
    method: "POST",
    headers: CONFIG.HEADERS,
    body: JSON.stringify({})
  })
  .then(async res => {
    let parsed = null;
    try {
      parsed = await res.clone().json();
    } catch (jsonError) {
      parsed = { parseError: String(jsonError) };
    }
    // #region agent log
    debugLog('pre-fix', 'H2', 'frontend/app.js:24', 'Fetch completed', {
      ok: res.ok,
      status: res.status,
      statusText: res.statusText,
      data: parsed
    });
    // #endregion
    return parsed;
  })
  .then(data => {
    // #region agent log
    debugLog('pre-fix', 'H3', 'frontend/app.js:35', 'Rendering response payload', {
      hasWeek: Boolean(data && data.week),
      weekType: data && data.week ? typeof data.week : 'missing'
    });
    // #endregion
    renderTable(data.week);
  })
  .catch(err => {
    // #region agent log
    debugLog('pre-fix', 'H4', 'frontend/app.js:43', 'Fetch/render failed', {
      errorName: err && err.name ? err.name : 'UnknownError',
      errorMessage: err && err.message ? err.message : String(err)
    });
    // #endregion
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
