# FastAPI Server

A FastAPI server with a blueprint-like modular structure for the Returnable project.

## Project Structure

```
server/
├── main.py                 # Main application entry point
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py       # Application configuration
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── api.py      # Main API router
│           └── endpoints/
│               ├── __init__.py
│               ├── health.py   # Health check endpoints
│               ├── users.py    # User management endpoints
│               └── items.py    # Item management endpoints
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables
└── .env.example          # Example environment file
```

## Features

- **Modular Structure**: Each feature has its own router (similar to Flask blueprints)
- **Health Checks**: Built-in health check endpoints
- **CORS Support**: Configurable CORS middleware
- **Environment Configuration**: Settings loaded from environment variables
- **Auto-generated Documentation**: Swagger UI and ReDoc available
- **Type Safety**: Full type hints with Pydantic models

## Setup and Installation

1. **Install dependencies**:

   ```bash
   cd server
   pip install -r requirements.txt
   ```

2. **Configure environment**:

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the server**:

   ```bash
   python main.py
   ```

   Or using uvicorn directly:

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Documentation

Once the server is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

## Available Endpoints

### Health Checks

- `GET /api/v1/health/` - Basic health check
- `GET /api/v1/health/detailed` - Detailed health information

### Users

- `GET /api/v1/users/` - Get all users
- `GET /api/v1/users/{user_id}` - Get user by ID
- `POST /api/v1/users/` - Create new user
- `PUT /api/v1/users/{user_id}` - Update user
- `DELETE /api/v1/users/{user_id}` - Delete user

### Items

- `GET /api/v1/items/` - Get all items (with pagination)
- `GET /api/v1/items/{item_id}` - Get item by ID
- `POST /api/v1/items/` - Create new item
- `PUT /api/v1/items/{item_id}` - Update item
- `DELETE /api/v1/items/{item_id}` - Delete item

## Adding New Endpoints

To add new endpoints (blueprints):

1. Create a new file in `app/api/v1/endpoints/`
2. Define your router and endpoints
3. Import and include the router in `app/api/v1/api.py`

Example:

```python
# app/api/v1/endpoints/products.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_products():
    return {"products": []}

# app/api/v1/api.py
from app.api.v1.endpoints import products

api_router.include_router(products.router, prefix="/products", tags=["products"])
```

## Configuration

The application can be configured using environment variables or the `.env` file:

- `PROJECT_NAME`: Application name
- `VERSION`: Application version
- `DEBUG`: Enable debug mode
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `BACKEND_CORS_ORIGINS`: Comma-separated list of allowed CORS origins

## Development

The server includes hot-reload functionality when running in debug mode. Any changes to the code will automatically restart the server.
