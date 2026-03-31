(function (root, factory) {
  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  root.MealPlannerModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function createEmptyNutrition() {
    return {
      calories: null,
      proteinGrams: null,
      carbsGrams: null,
      fatGrams: null
    };
  }

  function normalizeText(value) {
    if (typeof value !== "string") {
      return null;
    }

    const trimmed = value.trim();
    return trimmed || null;
  }

  function normalizeIngredients(ingredients) {
    if (!Array.isArray(ingredients)) {
      return [];
    }

    return ingredients
      .filter((ingredient) => ingredient && typeof ingredient === "object")
      .map((ingredient) => ({
        item: normalizeText(ingredient.item),
        amount: ingredient.amount ?? null,
        unit: normalizeText(ingredient.unit),
        preparation: normalizeText(ingredient.preparation)
      }))
      .filter((ingredient) => ingredient.item);
  }

  function normalizeInstructions(instructions) {
    if (!Array.isArray(instructions)) {
      return [];
    }

    return instructions
      .map((instruction, index) => {
        if (instruction && typeof instruction === "object") {
          return {
            step: instruction.step ?? index + 1,
            text: normalizeText(instruction.text)
          };
        }

        return {
          step: index + 1,
          text: normalizeText(instruction)
        };
      })
      .filter((instruction) => instruction.text);
  }

  function normalizeNutrition(nutrition) {
    const normalized = createEmptyNutrition();
    if (!nutrition || typeof nutrition !== "object") {
      return normalized;
    }

    Object.keys(normalized).forEach((key) => {
      normalized[key] = nutrition[key] ?? null;
    });
    return normalized;
  }

  function normalizeRecipe(recipe, mealKey) {
    if (!recipe) {
      return null;
    }

    if (typeof recipe === "string") {
      const title = normalizeText(recipe);
      return title
        ? {
            id: null,
            title,
            mealType: mealKey,
            diet: null,
            cuisine: null,
            sourceName: null,
            sourceUrl: null,
            ingredients: [],
            instructions: [],
            nutrition: createEmptyNutrition()
          }
        : null;
    }

    if (typeof recipe !== "object") {
      return null;
    }

    const title = normalizeText(recipe.title) || normalizeText(recipe.id);
    if (!title) {
      return null;
    }

    return {
      id: normalizeText(recipe.id),
      title,
      mealType: normalizeText(recipe.mealType) || mealKey,
      diet: normalizeText(recipe.diet),
      cuisine: normalizeText(recipe.cuisine),
      sourceName: normalizeText(recipe.sourceName),
      sourceUrl: normalizeText(recipe.sourceUrl),
      ingredients: normalizeIngredients(recipe.ingredients),
      instructions: normalizeInstructions(recipe.instructions),
      nutrition: normalizeNutrition(recipe.nutrition)
    };
  }

  function normalizeWeekData(rawWeek, weekDates) {
    const byDay = new Map();
    (rawWeek || []).forEach((entry) => {
      if (entry && entry.day) {
        byDay.set(entry.day, entry);
      }
    });

    return weekDates.slice(0, 7).map(({ day, dateLabel }) => {
      const source = byDay.get(day) || {};
      return {
        day,
        dateLabel,
        breakfast: normalizeRecipe(source.breakfast, "breakfast"),
        lunch: normalizeRecipe(source.lunch, "lunch"),
        snack: normalizeRecipe(source.snack, "snack"),
        dinner: normalizeRecipe(source.dinner, "dinner")
      };
    });
  }

  return {
    createEmptyNutrition,
    normalizeText,
    normalizeIngredients,
    normalizeInstructions,
    normalizeNutrition,
    normalizeRecipe,
    normalizeWeekData
  };
});
