from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_pipeline(client: TestClient):
    """Test pipeline creation."""
    pipeline_data = {
        "name": "test-pipeline",
        "description": "A test pipeline",
        "steps": [
            {
                "name": "step1",
                "description": "First step",
                "command": "echo 'Hello from step 1'"
            },
            {
                "name": "step2",
                "description": "Second step",
                "command": "echo 'Hello from step 2'"
            }
        ],
        "step_dependencies": []
    }

    response = client.post("/api/v1/pipelines/", json=pipeline_data)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "test-pipeline"
    assert data["description"] == "A test pipeline"
    assert "id" in data
    assert "created_at" in data


def test_list_pipelines(client: TestClient):
    """Test listing pipelines."""
    # First create a pipeline
    pipeline_data = {
        "name": "test-pipeline",
        "description": "A test pipeline",
        "steps": [
            {
                "name": "step1",
                "command": "echo 'test'"
            }
        ]
    }

    create_response = client.post("/api/v1/pipelines/", json=pipeline_data)
    assert create_response.status_code == 200

    # Now list pipelines
    list_response = client.get("/api/v1/pipelines/")
    assert list_response.status_code == 200

    pipelines = list_response.json()
    assert len(pipelines) == 1
    assert pipelines[0]["name"] == "test-pipeline"


def test_get_pipeline(client: TestClient):
    """Test getting a specific pipeline."""
    # First create a pipeline
    pipeline_data = {
        "name": "test-pipeline",
        "description": "A test pipeline",
        "steps": [
            {
                "name": "step1",
                "command": "echo 'test'"
            }
        ]
    }

    create_response = client.post("/api/v1/pipelines/", json=pipeline_data)
    assert create_response.status_code == 200

    pipeline_id = create_response.json()["id"]

    # Now get the pipeline
    get_response = client.get(f"/api/v1/pipelines/{pipeline_id}")
    assert get_response.status_code == 200

    pipeline = get_response.json()
    assert pipeline["name"] == "test-pipeline"
    assert pipeline["id"] == pipeline_id


def test_trigger_pipeline_run(client: TestClient):
    """Test triggering a pipeline run."""
    # First create a pipeline
    pipeline_data = {
        "name": "test-pipeline",
        "steps": [
            {
                "name": "step1",
                "command": "echo 'test'"
            }
        ]
    }

    create_response = client.post("/api/v1/pipelines/", json=pipeline_data)
    assert create_response.status_code == 200

    pipeline_id = create_response.json()["id"]

    # Now trigger a run
    run_response = client.post(f"/api/v1/pipelines/{pipeline_id}/trigger_run")
    assert run_response.status_code == 200

    run_data = run_response.json()
    assert run_data["pipeline_id"] == pipeline_id
    assert run_data["status"] == "pending"
    assert "id" in run_data


def test_list_pipeline_runs(client: TestClient):
    """Test listing pipeline runs."""
    # First create a pipeline and trigger a run
    pipeline_data = {
        "name": "test-pipeline",
        "steps": [
            {
                "name": "step1",
                "command": "echo 'test'"
            }
        ]
    }

    create_response = client.post("/api/v1/pipelines/", json=pipeline_data)
    pipeline_id = create_response.json()["id"]

    # Trigger a run
    client.post(f"/api/v1/pipelines/{pipeline_id}/trigger_run")

    # List runs
    runs_response = client.get(f"/api/v1/pipelines/{pipeline_id}/runs")
    assert runs_response.status_code == 200

    runs = runs_response.json()
    assert len(runs) == 1
    assert runs[0]["pipeline_id"] == pipeline_id


def test_get_pipeline_run(client: TestClient):
    """Test getting a specific pipeline run."""
    # First create a pipeline and trigger a run
    pipeline_data = {
        "name": "test-pipeline",
        "steps": [
            {
                "name": "step1",
                "command": "echo 'test'"
            }
        ]
    }

    create_response = client.post("/api/v1/pipelines/", json=pipeline_data)
    pipeline_id = create_response.json()["id"]

    # Trigger a run
    run_response = client.post(f"/api/v1/pipelines/{pipeline_id}/trigger_run")
    run_id = run_response.json()["id"]

    # Get the run
    get_run_response = client.get(f"/api/v1/pipelines/{pipeline_id}/runs/{run_id}")
    assert get_run_response.status_code == 200

    run_data = get_run_response.json()
    assert run_data["id"] == run_id
    assert run_data["pipeline_id"] == pipeline_id
