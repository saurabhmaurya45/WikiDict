# SM-WikiDict

A fast, high-performance dictionary service powered by Wikipedia. Features in-memory indexing with cloud-native storage to serve millions of word lookups with cost-effective, low-latency reads.

## Features

- **High Performance** - Sub-40ms p99 latency with in-memory index lookups
- **Cost Efficient** - Object storage + byte-range reads for minimal infrastructure cost
- **Scalable** - Handles 100K to 10M+ lookups per month
- **Zero Downtime Updates** - Blue-green deployment for safe, atomic data refreshes
- **Simple Operations** - Minimal moving parts, easy to maintain

## Architecture

The service uses a read-optimized architecture:

- **In-memory index** (~50MB) for O(1) key lookups
- **S3/GCS storage** for immutable data files
- **Byte-range HTTP reads** for precise value retrieval
- **Weekly changelog updates** with atomic version switching

## Tech Stack

- **Backend**: Python, FastAPI
- **Infrastructure**: AWS EKS, Terraform
- **Container**: Docker
- **Storage**: AWS S3 / GCS

## Project Structure

```
sm-wikidict/
├── main.py                    # FastAPI application entry point
├── requirement.txt            # Python dependencies
├── Dockerfile                 # Container image definition
│
├── src/
│   ├── controller/            # API endpoints
│   │   ├── health_controller.py   # /health, /ready endpoints
│   │   └── __init__.py
│   ├── service/               # Business logic
│   ├── middleware/            # Request/response middleware
│   ├── config/                # Configuration
│   └── utils/                 # Utility functions
│
└── deployment/
    └── terraform/             # Infrastructure as Code
        ├── infra-setup/       # S3 backend for Terraform state
        └── cluster/           # EKS cluster configuration
```

## Quick Start

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirement.txt

# Run the server
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Welcome message |
| `/health` | GET | Liveness probe (K8s) |
| `/ready` | GET | Readiness probe (K8s) |
| `/docs` | GET | Swagger UI documentation |

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready

# API docs
open http://localhost:8000/docs
```

## Infrastructure

See [deployment/terraform/README.md](deployment/terraform/README.md) for:
- AWS EKS cluster setup
- Single cluster with namespace-based environments (autoqa, prod)
- Terraform configuration and deployment instructions

## Documentation

- [Terraform Infrastructure Guide](deployment/terraform/README.md)
- [Architecture Review Board (ARB)](docs/architecture_review_board_arb_read_optimized_dictionary_system.md)

## License

MIT
