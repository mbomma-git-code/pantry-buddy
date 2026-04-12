(function (root, factory) {
  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  root.AppLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
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

  function formatMetaValue(value, fallback, normalizeText) {
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

  return {
    DAY_ORDER,
    MEAL_FIELDS,
    findFirstRecipe,
    formatMetaValue,
    formatIngredient,
    formatNutritionValue,
    getStartOfWeek,
    buildWeekDates,
    formatDateLabel,
    formatWeekRange,
    createEmptyWeek
  };
});
