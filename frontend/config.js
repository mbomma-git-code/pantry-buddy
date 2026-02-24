/**
 * Frontend Configuration
 * Centralized configuration for API endpoints and version management
 */

const CONFIG = {
  // API Version - Change this to switch between API versions
  API_VERSION: 'v1', // Options: 'v1', 'v2'
  
  // API Base URL
  API_BASE_URL: 'https://urneq69fyd.execute-api.us-east-2.amazonaws.com/prod',
  
  // API Endpoints by version
  ENDPOINTS: {
    v1: {
      generateMealPlan: '/generate-meal-plan'
    },
    v2: {
      generateMealPlan: '/v2/generate-meal-plan'
    }
  },
  
  // HTTP Headers
  HEADERS: {
    'Content-Type': 'application/json'
  },
  
  // UI Configuration
  UI: {
    tableColumns: ['Day', 'Breakfast', 'Lunch', 'Snack', 'Dinner']
  }
};

/**
 * Get the full API URL for a given endpoint
 * @param {string} endpointName - Name of the endpoint (e.g., 'generateMealPlan')
 * @returns {string} Full API URL
 */
function getApiUrl(endpointName) {
  const version = CONFIG.API_VERSION;
  const endpoint = CONFIG.ENDPOINTS[version]?.[endpointName];
  
  if (!endpoint) {
    throw new Error(`Endpoint '${endpointName}' not found for version '${version}'`);
  }
  
  return `${CONFIG.API_BASE_URL}${endpoint}`;
}
