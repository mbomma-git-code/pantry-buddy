const assert = require("node:assert/strict");
const path = require("node:path");

const { normalizeText } = require(path.join(__dirname, "../src/meal_planner_model.js"));
const AppLogic = require(path.join(__dirname, "../src/app_logic.js"));

const {
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
} = AppLogic;

function runTest(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

runTest("findFirstRecipe returns first meal with a title", () => {
  const week = [
    {
      day: "Monday",
      dateLabel: "Apr 1",
      breakfast: null,
      lunch: { title: "Soup" },
      snack: null,
      dinner: null
    }
  ];

  const first = findFirstRecipe(week);
  assert.equal(first.day, "Monday");
  assert.equal(first.mealKey, "lunch");
  assert.equal(first.recipe.title, "Soup");
});

runTest("findFirstRecipe skips empty slots", () => {
  const week = [
    {
      day: "Monday",
      dateLabel: "Apr 1",
      breakfast: null,
      lunch: null,
      snack: { title: "Apple" },
      dinner: null
    }
  ];

  const first = findFirstRecipe(week);
  assert.equal(first.mealKey, "snack");
});

runTest("findFirstRecipe returns null when no recipes", () => {
  assert.equal(
    findFirstRecipe([
      {
        day: "Monday",
        dateLabel: "Apr 1",
        breakfast: null,
        lunch: null,
        snack: null,
        dinner: null
      }
    ]),
    null
  );
});

runTest("formatMetaValue uses normalizeText and fallback", () => {
  assert.equal(formatMetaValue("  hello ", "fb", normalizeText), "hello");
  assert.equal(formatMetaValue(null, "fb", normalizeText), "fb");
});

runTest("formatIngredient joins amount, unit, item, preparation", () => {
  assert.equal(
    formatIngredient({
      amount: 2,
      unit: "cup",
      item: "rice",
      preparation: "rinsed"
    }),
    "2 cup rice (rinsed)"
  );
  assert.equal(formatIngredient({ item: "salt" }), "salt");
  assert.equal(formatIngredient({}), "Ingredient");
});

runTest("formatNutritionValue handles empty and suffix", () => {
  assert.equal(formatNutritionValue(null), "Not available");
  assert.equal(formatNutritionValue(100, " g"), "100 g");
});

runTest("getStartOfWeek returns Monday 00:00 local", () => {
  const wed = new Date(2026, 3, 1, 15, 30, 0);
  const start = getStartOfWeek(wed);
  assert.equal(start.getDay(), 1);
  assert.equal(start.getHours(), 0);
});

runTest("createEmptyWeek has seven days and null meals", () => {
  const weekDates = [
    { day: "Monday", date: new Date(2026, 3, 1) },
    { day: "Tuesday", date: new Date(2026, 3, 2) },
    { day: "Wednesday", date: new Date(2026, 3, 3) },
    { day: "Thursday", date: new Date(2026, 3, 4) },
    { day: "Friday", date: new Date(2026, 3, 5) },
    { day: "Saturday", date: new Date(2026, 3, 6) },
    { day: "Sunday", date: new Date(2026, 3, 7) }
  ];

  const week = createEmptyWeek(weekDates);
  assert.equal(week.length, 7);
  assert.equal(week[0].day, "Monday");
  assert.equal(week[0].breakfast, null);
  assert.ok(week[0].dateLabel);
});

runTest("formatWeekRange spans first and last day", () => {
  const weekDates = buildWeekDates();
  assert.equal(weekDates.length, 7);
  const label = formatWeekRange(weekDates);
  assert.ok(label.startsWith("Week of "));
  assert.ok(label.includes(" - "));
});

runTest("MEAL_FIELDS has four slots in breakfast-lunch-snack-dinner order", () => {
  assert.equal(MEAL_FIELDS.length, 4);
  assert.deepEqual(
    MEAL_FIELDS.map((m) => m.key),
    ["breakfast", "lunch", "snack", "dinner"]
  );
});

runTest("formatDateLabel returns short month and day", () => {
  const s = formatDateLabel(new Date(2026, 3, 2));
  assert.match(s, /Apr/);
  assert.match(s, /2/);
});
