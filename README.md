# Pulsr

Lightweight ML Pipeline Orchestration API that enables users to define, execute, and monitor ML pipelines.

## Setup

### Local Development

**Prerequisites:** Python 3.13+, UV package manager

```bash
# Clone and setup
git clone <repository-url>
cd pulsr

# Install dependencies
uv sync

# Run the server
uvicorn pulsr.main:app --reload
```

### Docker Setup

```bash
# Build and run
docker-compose up --build

# Access the application
open http://localhost:8000/api/v1/docs
```

## Documentation

### Project Design
- **[Project Design Document](docs/project.md)** - Complete system architecture, data models, and design decisions
- **[API Examples](docs/api-examples.md)** - Comprehensive HTTPie examples for all endpoints

### Interactive API Documentation
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

## Using the API

### Quick Examples
See [docs/api-examples.md](docs/api-examples.md) for complete HTTPie examples including:
- Creating pipelines with step dependencies
- Triggering pipeline runs
- Monitoring execution status
- Error handling examples

### Core Endpoints
- `POST /api/v1/pipelines` - Create pipeline with steps and dependencies
- `GET /api/v1/pipelines` - List all pipelines
- `GET /api/v1/pipelines/{id}` - Get pipeline details
- `POST /api/v1/pipelines/{id}/trigger_run` - Start new pipeline run
- `GET /api/v1/pipelines/{id}/runs` - List pipeline runs
- `GET /api/v1/pipelines/{id}/runs/{run_id}` - Get run details

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=pulsr tests/

# Run specific test file
uv run pytest tests/test_api.py
```

### Test Structure
- `tests/test_api.py` - API endpoint integration tests
- `tests/test_models.py` - Data model unit tests
- `tests/test_services.py` - Business logic tests
- `tests/conftest.py` - Test configuration and fixtures

## Development

### Adding New Features

1. **Models**: Add/modify data models in `pulsr/models/`
2. **Services**: Implement business logic in `pulsr/services/`
3. **API**: Create endpoints in `pulsr/api/v1/`
4. **Tests**: Add corresponding tests in `tests/`

### Project Structure
```
pulsr/
├── pulsr/                         # Main application package
│   ├── main.py                    # FastAPI app entry point
│   ├── core/                      # Configuration & database
│   ├── models/                    # SQLModel data models
│   ├── api/v1/                    # API endpoints
│   ├── services/                  # Business logic
│   └── utils/                     # Utility functions
├── tests/                         # Test suite
├── docs/                          # Documentation
└── pyproject.toml                 # Project configuration
```

### Environment Configuration

Create `.env` file for local development:
```env
DEBUG=true
DATABASE_URL=sqlite:///./pulsr.db
```

## Code Quality

```bash
# Format code
ruff format pulsr/ tests/

# Lint code  
ruff check pulsr/ tests/

# Fix auto-fixable linting issues
ruff check --fix pulsr/ tests/
```

### Architecture Principles
- **Clean Architecture**: Separated layers (API, Services, Models)
- **Type Safety**: Full type annotations with modern Python syntax
- **Dependency Injection**: FastAPI dependency system
- **Error Handling**: Custom exceptions with proper HTTP responses
- **Validation**: Comprehensive input validation and dependency cycle detection
