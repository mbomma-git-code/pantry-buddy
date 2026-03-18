const API_URL = typeof getApiUrl === "function"
  ? getApiUrl("generateMealPlan")
  : `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.v2.generateMealPlan}`;

const DAY_ORDER = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday"
];

const MEAL_FIELDS = [
  { key: "breakfast", label: "Breakfast", icon: "bi-cup-hot" },
  { key: "lunch", label: "Lunch", icon: "bi-flower1" },
  { key: "snack", label: "Snack", icon: "bi-apple" },
  { key: "dinner", label: "Dinner", icon: "bi-fork-knife" }
];

function getStartOfWeek(date) {
  const start = new Date(date);
  const dayIndex = start.getDay();
  const daysSinceMonday = (dayIndex + 6) % 7;
  start.setDate(start.getDate() - daysSinceMonday);
  start.setHours(0, 0, 0, 0);
  return start;
}

function buildWeekDates() {
  const start = getStartOfWeek(new Date());
  return DAY_ORDER.map((dayName, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    return {
      day: dayName,
      date
    };
  });
}

function formatDateLabel(date) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(date);
}

function formatWeekRange(weekDates) {
  const firstDate = weekDates[0].date;
  const lastDate = weekDates[6].date;
  return `Week of ${formatDateLabel(firstDate)} - ${formatDateLabel(lastDate)}`;
}

function createEmptyWeek(weekDates) {
  return weekDates.map(({ day, date }) => ({
    day,
    dateLabel: formatDateLabel(date),
    breakfast: "",
    lunch: "",
    snack: "",
    dinner: ""
  }));
}

function normalizeWeekData(rawWeek, weekDates) {
  const byDay = new Map();
  (rawWeek || []).forEach((entry) => {
    if (entry && entry.day) {
      byDay.set(entry.day, entry);
    }
  });

  return weekDates.slice(0, 7).map(({ day, date }) => {
    const source = byDay.get(day) || {};
    return {
      day,
      dateLabel: formatDateLabel(date),
      breakfast: source.breakfast || "",
      lunch: source.lunch || "",
      snack: source.snack || "",
      dinner: source.dinner || ""
    };
  });
}

function MealPlannerApp() {
  const weekDates = React.useMemo(() => buildWeekDates(), []);
  const [weekData, setWeekData] = React.useState(() => createEmptyWeek(weekDates));
  const [isLoading, setIsLoading] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState("");

  const weekRange = React.useMemo(() => formatWeekRange(weekDates), [weekDates]);

  const generateMealPlan = async () => {
    setIsLoading(true);
    setErrorMessage("");

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: CONFIG.HEADERS,
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      setWeekData(normalizeWeekData(data.week, weekDates));
    } catch (error) {
      console.error("Failed to generate meal plan", error);
      setErrorMessage("Failed to generate meal plan. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="planner-header">
        <div className="title-row">
          <span className="title-icon" aria-hidden="true">
            <i className="bi bi-egg-fried"></i>
          </span>
          <h1 className="planner-title">Meal Planner</h1>
        </div>
        <p className="planner-subtitle">Health is wealth! Let&apos;s add some delicious meals for the current week.</p>
        <p className="week-label">
          <i className="bi bi-calendar-week meal-icon" aria-hidden="true"></i>
          {" "}
          {weekRange}
        </p>
        <div className="toolbar">
          <button
            type="button"
            className="generate-btn"
            onClick={generateMealPlan}
            disabled={isLoading}
          >
            {isLoading ? "Generating..." : "Generate Meal Plan"}
          </button>
        </div>
        <div className="status">{errorMessage}</div>
      </header>

      <section className="week-grid" aria-label="Weekly meal plan">
        {weekData.slice(0, 7).map((day) => (
          <article key={day.day} className="day-card">
            <h2 className="day-name">{day.day}</h2>
            <p className="day-date">{day.dateLabel}</p>

            {MEAL_FIELDS.map((meal) => {
              const recipe = day[meal.key];
              const hasRecipe = Boolean(recipe && recipe.trim());
              const fallbackText = `No ${meal.label.toLowerCase()} planned`;

              return (
                <div className="meal-row" key={`${day.day}-${meal.key}`}>
                  <div className="meal-row-header">
                    <span className="meal-label">
                      <i className={`bi ${meal.icon} meal-icon`} aria-hidden="true"></i>
                      <span>{meal.label}</span>
                    </span>
                    <span className="plus-icon">+</span>
                  </div>
                  <div className={`meal-value${hasRecipe ? " has-recipe" : ""}`}>
                    {hasRecipe ? recipe : fallbackText}
                  </div>
                </div>
              );
            })}
          </article>
        ))}
      </section>
    </main>
  );
}

const rootElement = document.getElementById("root");
const root = ReactDOM.createRoot(rootElement);
root.render(<MealPlannerApp />);
