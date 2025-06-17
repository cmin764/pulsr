# Pulsr API Examples

This document provides examples of how to interact with the Pulsr ML Pipeline Orchestration API using HTTPie.

## Prerequisites

Make sure you have HTTPie installed and the Pulsr API running on `http://localhost:8000`.

```bash
# Install HTTPie
pip install httpie

# Or via Homebrew on macOS
brew install httpie
```

## API Examples

### 1. Create a Simple Pipeline

Create a basic pipeline with sequential steps:

```bash
http POST localhost:8000/api/v1/pipelines/ \
  name="simple-ml-pipeline" \
  description="A simple ML training pipeline" \
  steps:='[
    {
      "name": "data_preprocessing",
      "description": "Clean and prepare the data",
      "command": "python preprocess.py"
    },
    {
      "name": "model_training",
      "description": "Train the ML model",
      "command": "python train.py"
    },
    {
      "name": "model_evaluation",
      "description": "Evaluate model performance",
      "command": "python evaluate.py"
    }
  ]' \
  step_dependencies:='[]'
```

### 2. Create a Pipeline with Dependencies

Create a pipeline where steps depend on each other:

```bash
# First, create the pipeline and note the step IDs from the response
http POST localhost:8000/api/v1/pipelines/ \
  name="ml-pipeline-with-deps" \
  description="ML pipeline with step dependencies" \
  steps:='[
    {
      "name": "data_ingestion",
      "description": "Load raw data",
      "command": "python ingest.py"
    },
    {
      "name": "data_preprocessing", 
      "description": "Clean and prepare the data",
      "command": "python preprocess.py"
    },
    {
      "name": "feature_engineering",
      "description": "Create features for training",
      "command": "python features.py"
    },
    {
      "name": "model_training",
      "description": "Train the ML model",
      "command": "python train.py"
    },
    {
      "name": "model_evaluation",
      "description": "Evaluate model performance",
      "command": "python evaluate.py"
    }
  ]' \
  step_dependencies:='[{"step_name": "model_evaluation", "depends_on_step_name": "model_training"}]'
```

### 3. List All Pipelines

```bash
http GET localhost:8000/api/v1/pipelines/
```

### 4. Get Specific Pipeline Details

```bash
# Replace {pipeline_id} with actual pipeline ID
http GET localhost:8000/api/v1/pipelines/{pipeline_id}
```

### 5. Trigger a Pipeline Run

```bash
# Replace {pipeline_id} with actual pipeline ID
http POST localhost:8000/api/v1/pipelines/{pipeline_id}/trigger_run
```

### 6. List Pipeline Runs

```bash
# Replace {pipeline_id} with actual pipeline ID
http GET localhost:8000/api/v1/pipelines/{pipeline_id}/runs
```

### 7. Get Pipeline Run Details

```bash
# Replace {pipeline_id} and {run_id} with actual IDs
http GET localhost:8000/api/v1/pipelines/{pipeline_id}/runs/{run_id}
```

### 8. List Pipelines with Pagination

```bash
# Get first 10 pipelines
http GET localhost:8000/api/v1/pipelines/ skip==0 limit==10

# Get next 10 pipelines
http GET localhost:8000/api/v1/pipelines/ skip==10 limit==10
```

### 9. Complete Workflow Example

Here's a complete workflow from pipeline creation to run monitoring:

```bash
# 1. Create a pipeline
PIPELINE_RESPONSE=$(http POST localhost:8000/api/v1/pipelines/ \
  name="complete-example" \
  description="Complete workflow example" \
  steps:='[
    {
      "name": "setup",
      "description": "Setup environment",
      "command": "echo Setup complete"
    },
    {
      "name": "process",
      "description": "Process data", 
      "command": "echo Processing data"
    },
    {
      "name": "cleanup",
      "description": "Cleanup resources",
      "command": "echo Cleanup complete"
    }
  ]')

# 2. Extract pipeline ID (you would do this programmatically)
echo $PIPELINE_RESPONSE | jq '.id'

# 3. Trigger a run (replace PIPELINE_ID with actual ID)
RUN_RESPONSE=$(http POST localhost:8000/api/v1/pipelines/PIPELINE_ID/trigger_run)

# 4. Extract run ID
echo $RUN_RESPONSE | jq '.id'

# 5. Check run status (replace IDs with actual values)
http GET localhost:8000/api/v1/pipelines/PIPELINE_ID/runs/RUN_ID

# 6. List all runs for the pipeline
http GET localhost:8000/api/v1/pipelines/PIPELINE_ID/runs
```

## Response Examples

### Pipeline Creation Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "simple-ml-pipeline",
  "description": "A simple ML training pipeline",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "steps": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "data_preprocessing",
      "description": "Clean and prepare the data",
      "command": "python preprocess.py"
    }
  ]
}
```

### Pipeline Run Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "started_at": null,
  "completed_at": null,
  "created_at": "2024-01-15T10:35:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

## Error Handling

### Pipeline Not Found

```bash
http GET localhost:8000/api/v1/pipelines/invalid-id
# Returns 404 with error message
```

### Invalid Pipeline Definition

```bash
http POST localhost:8000/api/v1/pipelines/ \
  name="invalid-pipeline" \
  steps:='[]'
# Returns 400 with validation error
```

## Health Check

```bash
# Check API health
http GET localhost:8000/health

# API information
http GET localhost:8000/
```

## Interactive API Documentation

You can also explore the API interactively using the built-in documentation:

- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc 
