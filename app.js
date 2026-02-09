async function generateMealPlan() {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
  
    return {
      week: [
        {
          day: "Monday",
          breakfast: "Oatmeal with fruits",
          lunch: "Grilled vegetable bowl",
          snack: "Yogurt with nuts",
          dinner: "Paneer stir fry"
        },
        {
          day: "Tuesday",
          breakfast: "Poha",
          lunch: "Dal rice",
          snack: "Fruit bowl",
          dinner: "Vegetable khichdi"
        }
      ]
    };
  }


  async function handleGenerate() {
    const loadingEl = document.getElementById("loading");
    if (loadingEl) loadingEl.innerText = "Generating meal plan...";
    try {
      const response = await generateMealPlan();
      renderTable(response.week);
    } finally {
      if (loadingEl) loadingEl.innerText = "";
    }
  }
  
  function renderTable(weekData) {
    const tbody = document.querySelector("#mealTable tbody");
    tbody.innerHTML = "";
  
    weekData.forEach(day => {
      const row = document.createElement("tr");
  
      row.innerHTML = `
        <td>${day.day}</td>
        <td>${day.breakfast}</td>
        <td>${day.lunch}</td>
        <td>${day.snack}</td>
        <td>${day.dinner}</td>
      `;
  
      tbody.appendChild(row);
    });
  }
  