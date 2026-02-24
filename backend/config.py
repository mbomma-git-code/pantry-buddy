"""
Backend Configuration
Centralized configuration for AWS resources, API versions, and recipe paths
"""

import os

# API Version Configuration
# Change this to switch between API versions
API_VERSION = os.environ.get('API_VERSION', 'v1')  # Options: 'v1', 'v2'

# AWS Configuration
AWS_CONFIG = {
    'BUCKET_NAME': os.environ.get('S3_BUCKET_NAME', 'meal-plannerui-pantrybuddy'),
    'REGION': os.environ.get('AWS_REGION', 'us-east-2')
}

# Recipe Files Configuration
# Maps meal types to their S3 object keys
# Note: Local files are in data/recipes_json/, but S3 uses "recipes_json/" prefix
RECIPE_FILES = {
    "breakfast": "recipes_json/breakfast.json",
    "lunch": "recipes_json/lunch.json",
    "snack": "recipes_json/snack.json",
    "dinner": "recipes_json/dinner.json"
}

# API Endpoint Paths by Version
API_ENDPOINTS = {
    'v1': {
        'generate_meal_plan': '/generate-meal-plan'
    },
    'v2': {
        'generate_meal_plan': '/v2/generate-meal-plan'
    }
}

# HTTP Response Configuration
HTTP_CONFIG = {
    'DEFAULT_STATUS_CODE': 200,
    'HEADERS': {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }
}
