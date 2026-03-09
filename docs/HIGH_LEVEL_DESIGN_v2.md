# PantryBuddy - High-Level Design Documentation
## Weekly Meal Planner (V2 Update)

**Version:** 2.0  
**Date:** March 2026  
**Status:** V2 Baseline Stabilized

---

## 1. System Overview

### 1.1 Purpose
PantryBuddy is a web-based meal planning application that generates a weekly meal plan from curated recipe categories (breakfast, lunch, snack, dinner). V2 keeps the same user-facing flow while improving deployment alignment, API endpoint configuration, and version-readiness in backend contracts.

### 1.2 Key Features
- **Weekly Meal Plan Generation**: Automatically generates a 7-day plan
- **Random Recipe Selection**: Selects recipes from categorized lists
- **Simple Web Interface**: Static, low-latency UI for rapid interaction
- **Serverless Architecture**: API Gateway + Lambda + S3
- **Deployment Consistency**: Infrastructure and frontend deployment aligned to the same stack outputs

### 1.3 Target Users
- Individuals looking to simplify weekly meal planning
- Users who want variety in meals without manual curation
- Users who prefer a lightweight, no-login planner experience

---

## 2. System Architecture

### 2.1 High-Level Architecture

```text
┌─────────────────┐
│   Web Browser   │
│   (Frontend)    │
└────────┬────────┘
         │ HTTPS POST
         ▼
┌─────────────────────────┐
│   AWS API Gateway       │
│   (REST API Endpoint)   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   AWS Lambda Function   │
│   (Meal Plan Logic)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   AWS S3 Bucket         │
│   (Recipe Data Storage) │
└─────────────────────────┘
```

### 2.2 Architecture Components
1. **Frontend Layer** (`frontend/`)
   - Static HTML/CSS/JavaScript
   - Client-side rendering via `app.js`
   - API endpoint resolution via `config.js`

2. **API Layer** (AWS API Gateway)
   - Public REST endpoint
   - Route and method dispatch
   - CORS-enabled responses

3. **Backend Layer** (`backend/`)
   - Lambda handler with v1 and v2 route awareness
   - Recipe retrieval and weekly plan generation
   - Request validation hooks for v2-ready paths

4. **Data Layer** (AWS S3)
   - Recipe JSON files (`recipes_json/`)
   - Durable object storage for runtime reads

---

## 3. Component Details

### 3.1 Frontend Components

#### 3.1.1 `index.html`
- **Purpose**: Main UI layout
- **Key Elements**:
  - Meal plan generation button
  - Table container for displaying meal plans
  - Embedded CSS styling
- **Dependencies**: `app.js`, `config.js`

#### 3.1.2 `config.js`
- **Purpose**: Centralized endpoint/version configuration
- **Key Responsibilities**:
  - Resolve production API base URL
  - Provide local override for local debugging contexts
  - Map versioned endpoint paths
- **Current Production Base URL**: `https://bkq2ftn73g.execute-api.us-east-2.amazonaws.com/prod`

#### 3.1.3 `app.js`
- **Purpose**: Frontend request/response handling
- **Key Functions**:
  - `generateMealPlan()`: Sends POST to configured API endpoint
  - `renderTable(weekData)`: Renders returned week plan into HTML table

### 3.2 Backend Components

#### 3.2.1 `lambda_function.py`
- **Purpose**: Main Lambda entry point for meal planning
- **Key Functions**:
  - `lambda_handler(event, context)`: Route-aware entry point
  - `load_all_recipes()`: Loads all meal categories
  - `build_week_plan(recipes)`: Constructs 7-day meal plan
  - `handle_v2(event)`: v2-compatible request path with validation/retrieval hooks

#### 3.2.2 `config.py`
- **Purpose**: Runtime configuration for API endpoints, data source mode, and AWS settings
- **Key Values**:
  - Active endpoint map (`/v2/generate-meal-plan`)
  - `RECIPE_DATA_SOURCE` toggle (`s3` vs `local`)

### 3.3 Data Components

#### 3.3.1 Recipe JSON Files (`data/recipes_json/`)
- `breakfast.json`
- `lunch.json`
- `snack.json`
- `dinner.json`
- **Format**: JSON array of recipe names

---

## 4. Data Flow

### 4.1 Meal Plan Generation Flow

```text
1. User clicks "Generate Meal Plan"
2. Frontend sends POST /v2/generate-meal-plan
3. API Gateway invokes Lambda
4. Lambda loads recipe categories from S3
5. Lambda builds a 7-day meal plan
6. Lambda returns JSON payload
7. Frontend renders weekly table
```

### 4.2 Request/Response Contract

#### Request
```json
POST /v2/generate-meal-plan
Content-Type: application/json

{}
```

#### Response (Logical Payload)
```json
{
  "week": [
    {
      "day": "Monday",
      "breakfast": "Oatmeal with fruits",
      "lunch": "Dal rice",
      "snack": "Yogurt with nuts",
      "dinner": "Paneer stir fry"
    }
  ]
}
```

---

## 5. V1 vs V2 Differences

### 5.1 Summary Table

| Area | V1 | V2 |
|------|----|----|
| Frontend API target | Hardcoded historical API endpoint in docs and config | Updated to active stack API endpoint from current deployment |
| Frontend config model | Minimal direct endpoint usage | Centralized `config.js` with local override and version map |
| Version routing | Mostly v1 behavior, v2 noted as future | Route-aware Lambda with explicit v2 endpoint map and handler scaffold |
| Deployment workflows | Split/legacy UI deploy flow possible | Unified infrastructure workflow deploys frontend to stack `WebsiteBucketName` |
| UI bucket targeting | Risk of drift between buckets/regions | Deployment tied to CloudFormation stack output in `us-east-2` |
| Operational reliability | Manual reconciliation needed after endpoint changes | Automated sync path reduces stale frontend endpoint risk |

### 5.2 Practical Impact
- Reduces `Not Found` and `Missing Authentication Token` incidents caused by stale endpoint drift.
- Ensures frontend assets are deployed to the same bucket created/managed by CDK.
- Improves maintainability by keeping versioned endpoint logic centralized.

---

## 6. Technology Stack

### 6.1 Frontend
- HTML5
- CSS3
- JavaScript (ES6+)
- Fetch API

### 6.2 Backend
- Python 3.11 (Lambda runtime)
- AWS Lambda
- AWS API Gateway (REST)
- AWS S3
- `boto3`

### 6.3 Infrastructure and Delivery
- AWS CDK (TypeScript)
- GitHub Actions
- AWS IAM OIDC-based deploy role

---

## 7. Security and Reliability Considerations

### 7.1 Current State
- CORS currently allows all origins (`*`)
- No end-user auth for Phase 1 API
- Basic request validation in v2 code path

### 7.2 Recommended Next Steps
- Introduce CORS allowlist for known UI origins
- Add rate limiting and throttling strategy
- Add API auth strategy (API key/JWT/Cognito)
- Add error budget and rollback guidance in deployment runbook

---

## 8. Performance and Scalability

### 8.1 Current Characteristics
- Low compute complexity per request
- S3-backed recipe retrieval
- Lambda/API Gateway auto-scaling at service layer

### 8.2 Improvement Opportunities
- Cache recipe payload in-memory during warm Lambda lifecycle
- Add CloudFront distribution in front of website bucket
- Add integration/load tests in CI for endpoint health and latency

---

## 9. Deployment Model

### 9.1 Workflow
1. `Deploy Infrastructure (CDK)` workflow runs on `main` for infra/backend/frontend changes.
2. CDK deploy updates stack resources.
3. Workflow resolves `WebsiteBucketName` from stack outputs.
4. Workflow syncs `frontend/` to stack website bucket.

### 9.2 Key Outputs
- `WebsiteURL`
- `WebsiteBucketName`
- `ApiEndpoint`
- `GenerateMealPlanUrl`

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 2026 | Development Team | Initial high-level design document |
| 2.0 | Mar 2026 | Development Team | Added V2 architecture alignment, deployment flow updates, and V1 vs V2 comparison |

---

**End of Document**
