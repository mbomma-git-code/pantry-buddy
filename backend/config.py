"""
Backend Configuration
Centralized configuration for AWS resources, API versions, and recipe paths
"""

import os
from pathlib import Path

# API Version Configuration
# Change this to switch the default *meal-plan* client version (v1 legacy path, v2 planner).
# RAG v3 uses dedicated routes (/v3/chat, /v3/suggest-meals) regardless of this value.
API_VERSION = os.environ.get('API_VERSION', 'v2')  # Options: 'v1', 'v2'

# AWS Configuration
AWS_CONFIG = {
    'BUCKET_NAME': os.environ.get('S3_BUCKET_NAME', 'meal-plannerui-pantrybuddy'),
    'REGION': os.environ.get('AWS_REGION', 'us-east-2')
}

# Recipe data source configuration
# Use RECIPE_DATA_SOURCE=local during local debugging to read JSON files from disk
RECIPE_DATA_SOURCE = os.environ.get('RECIPE_DATA_SOURCE', 's3').strip().lower()
LOCAL_RECIPE_DATA_ROOT = os.environ.get(
    'LOCAL_RECIPE_DATA_ROOT',
    str(Path(__file__).resolve().parents[1] / 'data')
)

# Recipe Files Configuration
# Maps meal types to their S3 object keys
# Note: Local files are in data/recipes_json/, but S3 uses "recipes_json/" prefix
RECIPE_FILES = {
    "breakfast": "recipes_json/breakfast.json",
    "lunch": "recipes_json/lunch.json",
    "snack": "recipes_json/snack.json",
    "dinner": "recipes_json/dinner.json"
}

CANONICAL_RECIPE_FILE = os.environ.get(
    'CANONICAL_RECIPE_FILE',
    'recipes_json/recipes.json'
)
RECIPE_COMPATIBILITY_MODE = os.environ.get(
    'RECIPE_COMPATIBILITY_MODE',
    'auto'
).strip().lower()

# API Endpoint Paths by Version
API_ENDPOINTS = {
    'v1': {
        'generate_meal_plan': '/generate-meal-plan'
    },
    'v2': {
        'generate_meal_plan': '/v2/generate-meal-plan'
    },
    'v3': {
        'chat': '/v3/chat',
        'suggest_meals': '/v3/suggest-meals',
    },
}

# HTTP Response Configuration
HTTP_CONFIG = {
    'DEFAULT_STATUS_CODE': 200,
    'HEADERS': {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }
}

# RAG v3 configuration (chat retrieve-then-generate)
# When KNOWLEDGE_BASE_ID is set, Lambda uses Bedrock Retrieve; otherwise lexical catalog search.
DEFAULT_GENERATOR_MODEL_ID = 'anthropic.claude-3-5-haiku-20241022-v1:0'
DEFAULT_EMBEDDING_MODEL_ID = 'amazon.titan-embed-text-v2:0'

RAG_CONFIG = {
    # auto | bedrock | extract | fake
    'GENERATOR_MODE': os.environ.get('RAG_GENERATOR', 'auto').strip().lower(),
    'GENERATOR_MODEL_ID': os.environ.get(
        'GENERATOR_MODEL_ID',
        DEFAULT_GENERATOR_MODEL_ID,
    ),
    'EMBEDDING_MODEL_ID': os.environ.get(
        'EMBEDDING_MODEL_ID',
        DEFAULT_EMBEDDING_MODEL_ID,
    ),
    'KNOWLEDGE_BASE_ID': os.environ.get('KNOWLEDGE_BASE_ID', '').strip(),
    'MAX_TOKENS': int(os.environ.get('RAG_MAX_TOKENS', '1024')),
    'TEMPERATURE': float(os.environ.get('RAG_TEMPERATURE', '0.2')),
}
