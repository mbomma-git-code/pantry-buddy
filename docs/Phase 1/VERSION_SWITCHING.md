# Version Switching Guide

This document explains how to switch between API versions in the PantryBuddy application.

## Overview

The codebase has been refactored to use centralized configuration files, making version switching simple and consistent across frontend and backend.

## Configuration Files

### Frontend Configuration
- **File**: `frontend/config.js`
- **Key Setting**: `API_VERSION` (default: `'v1'`)

### Backend Configuration
- **File**: `backend/config.py`
- **Key Setting**: `API_VERSION` (default: `'v1'`)

## How to Switch Versions

### Option 1: Change Configuration File (Recommended)

#### Frontend
Edit `frontend/config.js`:
```javascript
const CONFIG = {
  API_VERSION: 'v2',  // Change from 'v1' to 'v2'
  // ... rest of config
};
```

#### Backend
Edit `backend/config.py`:
```python
API_VERSION = os.environ.get('API_VERSION', 'v2')  # Change default from 'v1' to 'v2'
```

### Option 2: Environment Variable (Backend Only)

Set the `API_VERSION` environment variable in your Lambda function:
```bash
export API_VERSION=v2
```

Or in AWS Lambda console:
- Go to Configuration → Environment variables
- Add: `API_VERSION` = `v2`

## Version-Specific Endpoints

### Version 1 (v1)
- **Frontend Endpoint**: `/generate-meal-plan`
- **Backend Handler**: Default handler in `lambda_handler()`
- **Features**: Basic random meal plan generation

### Version 2 (v2)
- **Frontend Endpoint**: `/v2/generate-meal-plan`
- **Backend Handler**: `handle_v2()` function
- **Features**: Enhanced features (to be implemented)

## Configuration Structure

### Frontend (`frontend/config.js`)
```javascript
const CONFIG = {
  API_VERSION: 'v1',
  API_BASE_URL: 'https://...',
  ENDPOINTS: {
    v1: { generateMealPlan: '/generate-meal-plan' },
    v2: { generateMealPlan: '/v2/generate-meal-plan' }
  }
};
```

### Backend (`backend/config.py`)
```python
API_VERSION = 'v1'
API_ENDPOINTS = {
    'v1': { 'generate_meal_plan': '/generate-meal-plan' },
    'v2': { 'generate_meal_plan': '/v2/generate-meal-plan' }
}
```

## Adding New Versions

### Step 1: Update Frontend Config
Add new version to `frontend/config.js`:
```javascript
ENDPOINTS: {
  v1: { generateMealPlan: '/generate-meal-plan' },
  v2: { generateMealPlan: '/v2/generate-meal-plan' },
  v3: { generateMealPlan: '/v3/generate-meal-plan' }  // New version
}
```

### Step 2: Update Backend Config
Add new version to `backend/config.py`:
```python
API_ENDPOINTS = {
    'v1': { 'generate_meal_plan': '/generate-meal-plan' },
    'v2': { 'generate_meal_plan': '/v2/generate-meal-plan' },
    'v3': { 'generate_meal_plan': '/v3/generate-meal-plan' }  # New version
}
```

### Step 3: Add Handler Function
Add handler in `backend/lambda_function.py`:
```python
def handle_v3(event):
    # Implementation for v3
    pass
```

### Step 4: Update Routing Logic
Update routing in `lambda_handler()`:
```python
v3_endpoint = API_ENDPOINTS['v3']['generate_meal_plan']
if path == v3_endpoint:
    return handle_v3(event)
```

## Benefits of This Approach

1. **Single Source of Truth**: Version configuration in one place
2. **Easy Switching**: Change one value to switch versions
3. **Consistency**: Frontend and backend stay in sync
4. **Maintainability**: Easy to add new versions
5. **Environment-Specific**: Can use environment variables for different deployments

## Testing Version Switching

1. **Frontend**: Change `API_VERSION` in `config.js` and verify the correct endpoint is called
2. **Backend**: Change `API_VERSION` in `config.py` or set environment variable and verify routing

## Notes

- Always ensure frontend and backend versions are compatible
- Test thoroughly after switching versions
- Keep backward compatibility when possible
- Document breaking changes between versions
