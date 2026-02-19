# Firestore Session for Google ADK

A specialized implementation of the `BaseSessionService` that uses Google Cloud Firestore for persisting application sessions, user states, and event logs.

## Overview

This package provides the `FirestoreSessionService` class, which handles the lifecycle of sessions within the Google ADK (Agent Development Kit) framework. It organizes data in a hierarchical Firestore structure:

- `apps/{app_name}`: Global application state.
- `apps/{app_name}/users/{user_id}`: Persistent user-specific state.
- `apps/{app_name}/users/{user_id}/sessions/{session_id}`: Individual session data and state.
- `apps/{app_name}/users/{user_id}/sessions/{session_id}/events/{event_id}`: Historical event logs for the session.

## Installation

You can include this package in your project's dependencies using the Git URL.

### Using `pip`
```bash
pip install git+https://github.com/mohammadshamma/firestore-session.git
```

### Using `uv` (pyproject.toml)
```toml
dependencies = [
    "firestore-session @ git+https://github.com/mohammadshamma/firestore-session.git"
]
```

## Configuration

The `FirestoreSessionService` can be configured via constructor arguments, environment variables, or through the Google ADK service registry.

### Precedence
1. **Constructor Arguments**: Explicit `project` and `database` passed to the class.
2. **Environment Variables**: `GOOGLE_CLOUD_PROJECT` and `GOOGLE_DATABASE`.
3. **Default Credentials**: Standard Google Cloud application default credentials.

## Usage with Google ADK

To use the `FirestoreSessionService` with Google ADK, register it with the ADK `ServiceRegistry`. This allows you to point your agents to Firestore using a URI.

### 1. Register the Service

In your main entry point (e.g., `serving.py`), define a factory function that parses the ADK URI.

```python
from urllib.parse import urlparse
from google.adk.cli.service_registry import get_service_registry
from firestore_session import FirestoreSessionService

def firestore_session_factory(uri: str, **kwargs):
    """
    Parses a URI like: firestore://my-gcp-project/my-database-instance
    """
    parsed = urlparse(uri)
    project_id = parsed.netloc or None
    # Remove leading slash from path to get database name
    database_id = parsed.path.lstrip('/') or None

    return FirestoreSessionService(
        project=project_id,
        database=database_id
    )

# Register the "firestore" scheme
get_service_registry().register_session_service("firestore", firestore_session_factory)
```

### 2. Configure the ADK App

Pass the URI to `get_fast_api_app`.

```python
from google.adk.cli.fast_api import get_fast_api_app

app = get_fast_api_app(
    agents_dir="path/to/agents",
    session_service_uri="firestore://my-project-id/my-database", 
    web=True
)
```

## Standalone Usage

```python
from google.cloud import firestore
from firestore_session import FirestoreSessionService

# Explicitly passing project/database
session_service = FirestoreSessionService(
    project="my-project-id",
    database="my-database"
)

# Or pass a pre-initialized AsyncClient
client = firestore.AsyncClient(project="p", database="d")
session_service = FirestoreSessionService(client=client)
```

## Dependencies

- `google-adk`: Core agent framework.
- `google-cloud-firestore`: Official Firestore client.
- `google-cloud-storage`: Used for extended state persistence.

## Development

### Running Tests
Tests use `pytest`. Ensure you have a Firestore emulator or a project configured for testing.

```bash
pytest tests/
```