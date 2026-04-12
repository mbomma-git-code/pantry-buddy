const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const INDEX_PATH = path.join(__dirname, "../src/index.html");

function runTest(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

runTest("index.html exposes root mount and required assets", () => {
  const html = fs.readFileSync(INDEX_PATH, "utf8");

  assert.match(html, /<div id="root"><\/div>/);
  assert.match(html, /charset="UTF-8"/i);
  assert.match(html, /<title>Meal Planner<\/title>/);
  assert.match(html, /react\.production\.min\.js/);
  assert.match(html, /react-dom\.production\.min\.js/);
  assert.match(html, /@babel\/standalone\/babel\.min\.js/);
  assert.match(html, /meal_planner_model\.js/);
  assert.match(html, /app_logic\.js/);
  assert.match(html, /app\.js/);
  assert.match(html, /config\.js/);
});

runTest("index.html loads app scripts after vendor bundles", () => {
  const html = fs.readFileSync(INDEX_PATH, "utf8");
  const reactIdx = html.indexOf("react.production.min.js");
  const configIdx = html.indexOf("config.js");
  const appIdx = html.indexOf('src="app.js');
  assert.ok(reactIdx !== -1 && configIdx !== -1 && appIdx !== -1);
  assert.ok(reactIdx < configIdx);
  assert.ok(configIdx < appIdx);
});
