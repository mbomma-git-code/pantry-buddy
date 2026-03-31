const API_URL = typeof getApiUrl === "function"
  ? getApiUrl("generateMealPlan")
  : `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.v2.generateMealPlan}`;
const {
  createEmptyNutrition,
  normalizeText,
  normalizeRecipe,
  normalizeWeekData
} = MealPlannerModel;

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

function findFirstRecipe(week) {
  for (const day of week) {
    for (const meal of MEAL_FIELDS) {
      const recipe = day[meal.key];
      if (recipe && recipe.title) {
        return {
          day: day.day,
          dateLabel: day.dateLabel,
          mealKey: meal.key,
          mealLabel: meal.label,
          recipe
        };
      }
    }
  }

  return null;
}

function formatMetaValue(value, fallback = "Not specified") {
  return normalizeText(value) || fallback;
}

function formatIngredient(ingredient) {
  const parts = [];
  if (ingredient.amount !== null && ingredient.amount !== undefined && ingredient.amount !== "") {
    parts.push(String(ingredient.amount));
  }
  if (ingredient.unit) {
    parts.push(ingredient.unit);
  }
  if (ingredient.item) {
    parts.push(ingredient.item);
  }

  let label = parts.join(" ").trim();
  if (!label) {
    label = "Ingredient";
  }

  if (ingredient.preparation) {
    label = `${label} (${ingredient.preparation})`;
  }

  return label;
}

function formatNutritionValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  return `${value}${suffix}`;
}

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
    breakfast: null,
    lunch: null,
    snack: null,
    dinner: null
  }));
}

function MealPlannerApp() {
  const weekDates = React.useMemo(() => buildWeekDates(), []);
  const [weekData, setWeekData] = React.useState(() => createEmptyWeek(weekDates));
  const [isLoading, setIsLoading] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState("");
  const [selectedMeal, setSelectedMeal] = React.useState(null);

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
      const normalizedWeek = normalizeWeekData(
        data.week,
        weekDates.map(({ day, date }) => ({
          day,
          dateLabel: formatDateLabel(date)
        }))
      );
      setWeekData(normalizedWeek);
      setSelectedMeal(findFirstRecipe(normalizedWeek));
    } catch (error) {
      console.error("Failed to generate meal plan", error);
      setErrorMessage("Failed to generate meal plan. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleMealSelect = (day, meal, recipe) => {
    setSelectedMeal({
      day: day.day,
      dateLabel: day.dateLabel,
      mealKey: meal.key,
      mealLabel: meal.label,
      recipe
    });
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

      <section className="planner-content">
        <section className="week-grid" aria-label="Weekly meal plan">
          {weekData.slice(0, 7).map((day) => (
            <article key={day.day} className="day-card">
              <h2 className="day-name">{day.day}</h2>
              <p className="day-date">{day.dateLabel}</p>

              {MEAL_FIELDS.map((meal) => {
                const recipe = day[meal.key];
                const hasRecipe = Boolean(recipe && recipe.title);
                const isSelected =
                  hasRecipe &&
                  selectedMeal &&
                  selectedMeal.day === day.day &&
                  selectedMeal.mealKey === meal.key;
                const fallbackText = `No ${meal.label.toLowerCase()} planned`;

                return (
                  <div className="meal-row" key={`${day.day}-${meal.key}`}>
                    <div className="meal-row-header">
                      <span className="meal-label">
                        <i className={`bi ${meal.icon} meal-icon`} aria-hidden="true"></i>
                        <span>{meal.label}</span>
                      </span>
                      <span className="plus-icon">{hasRecipe ? "View" : "+"}</span>
                    </div>
                    {hasRecipe ? (
                      <button
                        type="button"
                        className={`meal-value has-recipe recipe-trigger${isSelected ? " is-selected" : ""}`}
                        onClick={() => handleMealSelect(day, meal, recipe)}
                      >
                        {recipe.title}
                      </button>
                    ) : (
                      <div className="meal-value">{fallbackText}</div>
                    )}
                  </div>
                );
              })}
            </article>
          ))}
        </section>

        <aside className="recipe-panel" aria-live="polite">
          {selectedMeal ? (
            <React.Fragment>
              <p className="recipe-panel-context">
                {selectedMeal.day} | {selectedMeal.dateLabel} | {selectedMeal.mealLabel}
              </p>
              <h2 className="recipe-panel-title">{selectedMeal.recipe.title}</h2>

              <div className="recipe-meta-grid">
                <div className="recipe-meta-item">
                  <span className="recipe-meta-label">Meal type</span>
                  <span className="recipe-meta-value">
                    {formatMetaValue(selectedMeal.recipe.mealType, selectedMeal.mealLabel)}
                  </span>
                </div>
                <div className="recipe-meta-item">
                  <span className="recipe-meta-label">Diet</span>
                  <span className="recipe-meta-value">
                    {formatMetaValue(selectedMeal.recipe.diet)}
                  </span>
                </div>
                <div className="recipe-meta-item">
                  <span className="recipe-meta-label">Cuisine</span>
                  <span className="recipe-meta-value">
                    {formatMetaValue(selectedMeal.recipe.cuisine)}
                  </span>
                </div>
                <div className="recipe-meta-item">
                  <span className="recipe-meta-label">Source</span>
                  <span className="recipe-meta-value">
                    {formatMetaValue(selectedMeal.recipe.sourceName)}
                  </span>
                </div>
              </div>

              {selectedMeal.recipe.sourceUrl ? (
                <p className="recipe-source-link-row">
                  <a
                    className="recipe-source-link"
                    href={selectedMeal.recipe.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View original recipe
                    <i className="bi bi-box-arrow-up-right" aria-hidden="true"></i>
                  </a>
                </p>
              ) : null}

              <section className="recipe-detail-section">
                <h3>Ingredients</h3>
                {selectedMeal.recipe.ingredients.length ? (
                  <ul className="recipe-list">
                    {selectedMeal.recipe.ingredients.map((ingredient, index) => (
                      <li key={`${selectedMeal.recipe.id || selectedMeal.recipe.title}-ingredient-${index}`}>
                        {formatIngredient(ingredient)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="recipe-empty">Ingredients are not available for this recipe yet.</p>
                )}
              </section>

              <section className="recipe-detail-section">
                <h3>Instructions</h3>
                {selectedMeal.recipe.instructions.length ? (
                  <ol className="recipe-list recipe-list-numbered">
                    {selectedMeal.recipe.instructions.map((instruction) => (
                      <li
                        key={`${selectedMeal.recipe.id || selectedMeal.recipe.title}-instruction-${instruction.step}`}
                      >
                        {instruction.text}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="recipe-empty">Instructions are not available for this recipe yet.</p>
                )}
              </section>

              <section className="recipe-detail-section">
                <h3>Nutrition</h3>
                <div className="nutrition-grid">
                  <div className="nutrition-item">
                    <span className="nutrition-label">Calories</span>
                    <span className="nutrition-value">
                      {formatNutritionValue(selectedMeal.recipe.nutrition.calories)}
                    </span>
                  </div>
                  <div className="nutrition-item">
                    <span className="nutrition-label">Protein</span>
                    <span className="nutrition-value">
                      {formatNutritionValue(selectedMeal.recipe.nutrition.proteinGrams, " g")}
                    </span>
                  </div>
                  <div className="nutrition-item">
                    <span className="nutrition-label">Carbs</span>
                    <span className="nutrition-value">
                      {formatNutritionValue(selectedMeal.recipe.nutrition.carbsGrams, " g")}
                    </span>
                  </div>
                  <div className="nutrition-item">
                    <span className="nutrition-label">Fat</span>
                    <span className="nutrition-value">
                      {formatNutritionValue(selectedMeal.recipe.nutrition.fatGrams, " g")}
                    </span>
                  </div>
                </div>
              </section>
            </React.Fragment>
          ) : (
            <div className="recipe-panel-empty">
              <h2 className="recipe-panel-title">Recipe details</h2>
              <p className="recipe-empty">
                Generate a meal plan and click any meal to view its recipe details here.
              </p>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

const rootElement = document.getElementById("root");
const root = ReactDOM.createRoot(rootElement);
root.render(<MealPlannerApp />);
