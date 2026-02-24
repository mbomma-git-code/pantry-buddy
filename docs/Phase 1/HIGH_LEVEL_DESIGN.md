# PantryBuddy - High-Level Design Documentation
## Phase 1: Weekly Meal Planner

**Version:** 1.0  
**Date:** February 2026  
**Status:** Phase 1 - Initial Implementation

---

## 1. System Overview

### 1.1 Purpose
PantryBuddy is a web-based meal planning application that generates personalized weekly meal plans. The system helps users plan their meals for the week by randomly selecting recipes from predefined categories (breakfast, lunch, snack, dinner).

### 1.2 Key Features
- **Weekly Meal Plan Generation**: Automatically generates a 7-day meal plan
- **Random Recipe Selection**: Selects recipes randomly from predefined categories
- **Simple Web Interface**: Clean, user-friendly interface for viewing meal plans
- **Serverless Architecture**: Built on AWS Lambda for scalability and cost-effectiveness

### 1.3 Target Users
- Individuals looking to simplify meal planning
- Users who want variety in their weekly meals
- People seeking a quick solution for meal planning

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────┐
│   Web Browser   │
│   (Frontend)    │
└────────┬────────┘
         │ HTTPS POST
         │
         ▼
┌─────────────────────────┐
│   AWS API Gateway       │
│   (REST API Endpoint)   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   AWS Lambda Function   │
│   (Backend Logic)        │
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
   - Client-side rendering
   - API communication via POST API

2. **API Layer** (AWS API Gateway)
   - RESTful API endpoint
   - Request routing
   - CORS handling

3. **Backend Layer** (`backend/`)
   - AWS Lambda function
   - Business logic processing
   - Recipe selection algorithm

4. **Data Layer** (AWS S3)
   - Recipe JSON files storage
   - Persistent data repository

---

## 3. Component Details

### 3.1 Frontend Components

#### 3.1.1 `index.html`
- **Purpose**: Main HTML structure and UI layout
- **Key Elements**:
  - Meal plan generation button
  - Table container for displaying meal plans
  - Embedded CSS styling
- **Dependencies**: `app.js`

#### 3.1.2 `app.js`
- **Purpose**: Frontend application logic
- **Key Functions**:
  - `generateMealPlan()`: Initiates API call to backend
  - `renderTable(weekData)`: Renders meal plan data in HTML table
- **API Endpoint**: `https://urneq69fyd.execute-api.us-east-2.amazonaws.com/prod/generate-meal-plan`

### 3.2 Backend Components

#### 3.2.1 `lambda_function.py`
- **Purpose**: AWS Lambda handler for meal plan generation
- **Key Functions**:
  - `lambda_handler(event, context)`: Main entry point
  - `load_recipes(key)`: Fetches recipe lists from S3
  - `handle_v2(event)`: Future v2 API handler (placeholder)
- **Dependencies**: `boto3`, `json`, `random`

### 3.3 Data Components

#### 3.3.1 Recipe JSON Files (`data/recipes_json/`)
- **Structure**: Array of recipe name strings
- **Files**:
  - `breakfast.json`: Breakfast recipe options
  - `lunch.json`: Lunch recipe options
  - `snack.json`: Snack recipe options
  - `dinner.json`: Dinner recipe options
- **Format**: JSON array, e.g., `["Recipe 1", "Recipe 2", ...]`

#### 3.3.2 Recipe Text Files (`data/recipes_text/`)
- **Purpose**: Detailed recipe instructions (future use)
- **Format**: Plain text files with recipe details

---

## 4. Data Flow

### 4.1 Meal Plan Generation Flow

```
1. User clicks "Generate Meal Plan" button
   ↓
2. Frontend (app.js) sends POST request to API Gateway
   ↓
3. API Gateway routes request to Lambda function
   ↓
4. Lambda function:
   a. Loads all recipe JSON files from S3
   b. For each day (Monday-Sunday):
      - Randomly selects one breakfast recipe
      - Randomly selects one lunch recipe
      - Randomly selects one snack recipe
      - Randomly selects one dinner recipe
   c. Builds week_plan array
   d. Returns JSON response
   ↓
5. Frontend receives response
   ↓
6. Frontend renders meal plan table
```

### 4.2 Request/Response Format

#### Request
```json
POST /generate-meal-plan
Content-Type: application/json

{}
```

#### Response
```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  },
  "body": {
    "week": [
      {
        "day": "Monday",
        "breakfast": "Oatmeal with fruits",
        "lunch": "Dal rice",
        "snack": "Yogurt with nuts",
        "dinner": "Paneer stir fry"
      },
      {
        "day": "Tuesday",
        "breakfast": "Poha",
        "lunch": "Veg Pulao",
        "snack": "Fruit bowl",
        "dinner": "Vegetable khichdi"
      },
      ... (7 days total)
    ]
  }
}
```

---

## 5. Technology Stack

### 5.1 Frontend
- **HTML5**: Structure and markup
- **CSS3**: Styling and layout
- **JavaScript (ES6+)**: Client-side logic
- **Fetch API**: HTTP requests

### 5.2 Backend
- **Python 3.x**: Lambda runtime
- **AWS Lambda**: Serverless compute
- **AWS API Gateway**: API management
- **AWS S3**: Object storage
- **boto3**: AWS SDK for Python

### 5.3 Infrastructure
- **AWS Cloud**: Hosting and services
- **Git**: Version control

---

## 6. Project Structure

```
PantryBuddy/
├── frontend/                 # Client-side application
│   ├── index.html           # Main HTML file
│   └── app.js               # Frontend JavaScript logic
│
├── backend/                 # Server-side code
│   └── lambda_function.py   # AWS Lambda handler
│
├── data/                    # Data and assets
│   ├── recipes_json/        # JSON recipe lists (for Lambda)
│   │   ├── breakfast.json
│   │   ├── lunch.json
│   │   ├── snack.json
│   │   └── dinner.json
│   └── recipes_text/        # Detailed recipe text files
│
├── docs/                    # Documentation
│   └── Phase 1/
│       └── HIGH_LEVEL_DESIGN.md
│
├── infrastructure/          # Deployment & infrastructure configs
│                            # (Ready for Terraform, CloudFormation, etc.)
│
├── .git/                    # Git repository
└── .github/                 # GitHub workflows
```

---

## 7. API Design

### 7.1 Endpoint: Generate Meal Plan

**Endpoint**: `POST /generate-meal-plan`

**Description**: Generates a weekly meal plan with random recipe selections.

**Request**:
- Method: `POST`
- Headers: `Content-Type: application/json`
- Body: Empty JSON object `{}`

**Response**:
- Status Code: `200`
- Headers: 
  - `Content-Type: application/json`
  - `Access-Control-Allow-Origin: *`
- Body: JSON object with `week` array containing 7 day objects

**Error Handling**:
- Frontend displays alert on API failure
- Lambda returns appropriate HTTP status codes

---

## 8. Design Decisions

### 8.1 Serverless Architecture
- **Rationale**: Cost-effective, scalable, no server management
- **Trade-offs**: Cold start latency, vendor lock-in

### 8.2 Random Selection Algorithm
- **Rationale**: Simple, provides variety
- **Trade-offs**: No personalization, potential repetition

### 8.3 S3 for Recipe Storage
- **Rationale**: Simple, cost-effective, scalable
- **Trade-offs**: No query capabilities, requires full file reads

### 8.4 Static Frontend
- **Rationale**: Fast loading, simple deployment
- **Trade-offs**: Limited interactivity, no offline support

---

## 9. Security Considerations

### 9.1 Current Implementation
- CORS enabled for all origins (`*`)
- No authentication/authorization
- No input validation (empty request body)

### 9.2 Future Enhancements
- Implement CORS whitelist
- Add API key authentication
- Input validation and sanitization
- Rate limiting

---

## 10. Performance Considerations

### 10.1 Current Optimizations
- Single S3 read per recipe category (4 reads total)
- In-memory processing
- Minimal data transfer

### 10.2 Potential Improvements
- S3 caching for recipe lists
- Batch S3 reads
- Response compression
- CDN for frontend assets

---

## 11. Scalability

### 11.1 Current Capacity
- Lambda: Handles concurrent requests automatically
- S3: Virtually unlimited storage
- API Gateway: Handles high request volumes

### 11.2 Limitations
- Recipe list size (currently small JSON files)
- No database for complex queries
- Single Lambda function handles all logic

---

## 12. Future Enhancements (Phase 2+)

### 12.1 Planned Features
- **User Preferences**: Dietary restrictions, allergies, preferences
- **Recipe Details**: Full recipe instructions and ingredients
- **Shopping List**: Generate shopping list from meal plan
- **Meal History**: Track past meal plans
- **Nutritional Information**: Calories, macros per meal
- **Custom Recipes**: User-defined recipe additions
- **AI Integration**: Smart meal suggestions based on preferences

### 12.2 Technical Improvements
- Database integration (DynamoDB or RDS)
- User authentication and profiles
- Advanced filtering and search
- Recipe recommendation engine
- Mobile app support
- Offline functionality

### 12.3 API Versioning
- Current: `/generate-meal-plan` (v1)
- Planned: `/v2/generate-meal-plan` (with enhanced features)
- Backward compatibility maintained

---

## 13. Deployment

### 13.1 Frontend Deployment
- Static hosting 
- No build process required

### 13.2 Backend Deployment
- AWS Lambda via AWS Console, CLI, or Infrastructure as Code
- API Gateway configuration
- S3 bucket setup with recipe files

### 13.3 Configuration
- API Gateway endpoint URL in `app.js`
- S3 bucket name in `lambda_function.py`
- IAM roles and permissions for Lambda

---

## 14. Testing Strategy

### 14.1 Current State
- Manual testing via web interface
- No automated tests

### 14.2 Recommended Testing
- **Unit Tests**: Lambda function logic
- **Integration Tests**: API Gateway + Lambda + S3
- **E2E Tests**: Frontend + Backend flow
- **Load Tests**: Concurrent request handling

---

## 15. Monitoring and Logging

### 15.1 Current State
- AWS CloudWatch logs for Lambda
- Browser console for frontend errors

### 15.2 Recommended Enhancements
- CloudWatch dashboards
- Error tracking (Sentry, etc.)
- Performance monitoring
- Usage analytics

---

## 16. Documentation

### 16.1 Current Documentation
- This high-level design document
- Inline code comments

### 16.2 Recommended Additions
- API documentation (OpenAPI/Swagger)
- Developer setup guide
- Deployment runbook
- User guide

---

## 17. Glossary

- **Lambda**: AWS Lambda serverless compute service
- **S3**: Amazon Simple Storage Service
- **API Gateway**: AWS API Gateway service
- **CORS**: Cross-Origin Resource Sharing
- **JSON**: JavaScript Object Notation
- **REST**: Representational State Transfer

---

## 18. References

- AWS Lambda Documentation
- AWS API Gateway Documentation
- AWS S3 Documentation
- Project Repository: `https://github.com/mbomma-git-code/pantry-buddy`

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 2026 | Development Team | Initial high-level design document |

---

**End of Document**
