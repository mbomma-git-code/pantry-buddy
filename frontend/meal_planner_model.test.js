const assert = require("node:assert/strict");

const {
  createEmptyNutrition,
  normalizeRecipe,
  normalizeWeekData
} = require("./meal_planner_model.js");

function runTest(name, callback) {
  try {
    callback();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

runTest("normalizeRecipe preserves source attribution and filters invalid details", () => {
  const recipe = normalizeRecipe(
    {
      id: " kale-salad ",
      title: "  Kale Salad  ",
      mealType: " lunch ",
      diet: " vegetarian ",
      cuisine: " American ",
      sourceName: " Love and Lemons ",
      sourceUrl: " https://www.loveandlemons.com/kale-salad/ ",
      ingredients: [
        { item: " Kale ", amount: 1, unit: " bunch ", preparation: " chopped " },
        { item: "   ", amount: 2, unit: "tbsp" }
      ],
      instructions: [
        { step: 4, text: " Toss and serve. " },
        { text: "   " }
      ],
      nutrition: {
        calories: 320,
        proteinGrams: 9
      }
    },
    "lunch"
  );

  assert.deepEqual(recipe, {
    id: "kale-salad",
    title: "Kale Salad",
    mealType: "lunch",
    diet: "vegetarian",
    cuisine: "American",
    sourceName: "Love and Lemons",
    sourceUrl: "https://www.loveandlemons.com/kale-salad/",
    ingredients: [
      {
        item: "Kale",
        amount: 1,
        unit: "bunch",
        preparation: "chopped"
      }
    ],
    instructions: [
      {
        step: 4,
        text: "Toss and serve."
      }
    ],
    nutrition: {
      calories: 320,
      proteinGrams: 9,
      carbsGrams: null,
      fatGrams: null
    }
  });
});

runTest("normalizeWeekData returns normalized recipe objects for API week payloads", () => {
  const weekDates = [
    { day: "Monday", dateLabel: "Mar 30" },
    { day: "Tuesday", dateLabel: "Mar 31" }
  ];

  const normalizedWeek = normalizeWeekData(
    [
      {
        day: "Monday",
        breakfast: " Berry Oats ",
        lunch: {
          title: "Veg Wrap",
          sourceName: "Lunch Lab",
          sourceUrl: "https://example.test/veg-wrap",
          nutrition: { calories: 410 }
        }
      }
    ],
    weekDates
  );

  assert.equal(normalizedWeek.length, 2);
  assert.deepEqual(normalizedWeek[0].breakfast, {
    id: null,
    title: "Berry Oats",
    mealType: "breakfast",
    diet: null,
    cuisine: null,
    sourceName: null,
    sourceUrl: null,
    ingredients: [],
    instructions: [],
    nutrition: createEmptyNutrition()
  });
  assert.equal(normalizedWeek[0].lunch.sourceName, "Lunch Lab");
  assert.equal(normalizedWeek[0].lunch.sourceUrl, "https://example.test/veg-wrap");
  assert.equal(normalizedWeek[0].lunch.nutrition.calories, 410);
  assert.equal(normalizedWeek[1].day, "Tuesday");
  assert.equal(normalizedWeek[1].dateLabel, "Mar 31");
  assert.equal(normalizedWeek[1].dinner, null);
});
