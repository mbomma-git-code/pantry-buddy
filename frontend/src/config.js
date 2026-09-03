/**
 * Frontend Configuration
 * Centralized configuration for API endpoints and version management
 */

const PROD_API_BASE_URL = 'https://bkq2ftn73g.execute-api.us-east-2.amazonaws.com/prod';
const DEFAULT_LOCAL_API_BASE_URL = 'http://127.0.0.1:8000';
const LOCAL_API_OVERRIDE_STORAGE_KEY = 'pantrybuddy.localApiBaseUrl';

function isLocalPageContext() {
  const hostname = window.location.hostname;
  return window.location.protocol === 'file:' || hostname === '127.0.0.1' || hostname === 'localhost';
}

function isAllowedLocalApiUrl(value) {
  if (!value) {
    return false;
  }

  try {
    const parsed = new URL(value);
    return parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost';
  } catch (error) {
    console.warn('Ignoring invalid local API override URL.', error);
    return false;
  }
}

function getLocalApiOverride() {
  if (!isLocalPageContext()) {
    return null;
  }

  const params = new URLSearchParams(window.location.search);
  const queryOverride = params.get('apiBaseUrl');
  if (isAllowedLocalApiUrl(queryOverride)) {
    return queryOverride;
  }

  const storedOverride = window.localStorage.getItem(LOCAL_API_OVERRIDE_STORAGE_KEY);
  if (isAllowedLocalApiUrl(storedOverride)) {
    return storedOverride;
  }

  return DEFAULT_LOCAL_API_BASE_URL;
}

const CONFIG = {
  // API Version - Change this to switch between API versions
  API_VERSION: 'v2', // Options: 'v1', 'v2'

  // API Base URL
  API_BASE_URL: getLocalApiOverride() || PROD_API_BASE_URL,

  // API Endpoints by version
  ENDPOINTS: {
    v1: {
      generateMealPlan: '/generate-meal-plan'
    },
    v2: {
      generateMealPlan: '/v2/generate-meal-plan'
    },
    // RAG v3: separate from the weekly planner; use getApiUrl with API_VERSION 'v3' when calling.
    v3: {
      chat: '/v3/chat',
      suggestMeals: '/v3/suggest-meals'
    }
  },
  
  // HTTP Headers
  HEADERS: {
    'Content-Type': 'application/json'
  }
};

/**
 * Get the full API URL for a given endpoint
 * @param {string} endpointName - Name of the endpoint (e.g., 'generateMealPlan', 'chat')
 * @param {string} [versionOverride] - Optional API version key (e.g., 'v3' for RAG routes)
 * @returns {string} Full API URL
 */
function getApiUrl(endpointName, versionOverride) {
  const version = versionOverride ?? CONFIG.API_VERSION;
  const endpoint = CONFIG.ENDPOINTS[version]?.[endpointName];

  if (!endpoint) {
    throw new Error(`Endpoint '${endpointName}' not found for version '${version}'`);
  }

  return `${CONFIG.API_BASE_URL}${endpoint}`;
}
