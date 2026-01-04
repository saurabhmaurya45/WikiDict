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
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
├── Dockerfile                 # Container image definition
├── version.txt                # Application version
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
├── .github/
│   ├── workflows/             # GitHub Actions CI/CD
│   │   ├── build.yml          # PR build & quality checks
│   │   ├── release.yml        # Production release pipeline
│   │   ├── ci-build-wikidict.yml  # WikiDict artifact builder
│   │   └── cleanup-ecr-images.yml # ECR image cleanup
│   ├── CODEOWNERS             # Code ownership rules
│   └── pull_request_template.md # PR template
│
├── k8s/                       # Kubernetes manifests
│   ├── namespace.yaml         # Environment namespaces
│   ├── deployment.yaml        # Application deployment
│   └── service.yaml           # LoadBalancer service
│
├── scripts/                   # Build & utility scripts
│   ├── build_wikidict.py      # Incremental WikiDict build
│   ├── build_wikidict_full.py # Full WikiDict rebuild
│   └── generate_fake_dataset.py  # Test data generator
│
├── experiments/               # Learning experiments & guides
│   ├── README.md              # Experiments index
│   └── 01-local-k8s-deployment/  # Phase 1: Local K8s
│       ├── README.md          # Complete guide
│       ├── commands.sh        # Command reference
│       └── troubleshooting.md # Debug guide
│
├── docs/                      # Documentation
│   ├── architecture_review_board_arb_read_optimized_dictionary_system.md
│   └── infrastructure-costing-decisions.md
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
pip install -r requirements.txt

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

## CI/CD Pipeline

### GitHub Actions Workflows

The project uses four automated workflows:

**1. Branch Build (`build.yml`)** - Runs on pull requests
- Semantic versioning with timestamps
- Security scans: Bandit (SAST), Safety (dependencies), Ruff (linting)
- Code quality: Black, Flake8, Mypy
- Container image build validation
- Artifact retention (2 days)

**2. Release Build (`release.yml`)** - Runs on push to main
- Triggers automatically or manually via workflow_dispatch
- Runs all quality gates in parallel
- Builds and pushes Docker image to AWS ECR Public
- Creates GitHub release with version tracking
- Full audit trail (version, triggered_by)

**3. WikiDict Builder (`ci-build-wikidict.yml`)** - Scheduled daily
- Multi-environment support (production/autoqa)
- Incremental updates with changelog processing
- S3 artifact upload with manifest tracking
- Automatically triggers release workflow on success

**4. ECR Image Cleanup (`cleanup-ecr-images.yml`)** - Scheduled every 15 days
- Automated cleanup of old Docker images from ECR Public
- Retention policy: Keep last 10 images OR images newer than 15 days
- Manual trigger available via workflow_dispatch
- Prevents storage bloat and manages costs

### Required GitHub Secrets & Variables

**Secrets:**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (ECR authentication)
- `PROD_ACCESS_KEY`, `PROD_SECRET_KEY` (Production S3)
- `AUTOQA_ACCESS_KEY`, `AUTOQA_SECRET_KEY` (AutoQA S3)

**Variables:**
- `AWS_REGION` (e.g., eu-north-1 for EKS/S3, us-east-1 for ECR Public)
- `WIKIDICT_SERVICE_ECR_REPO` (ECR Public repository URL)
- `PRODUCTION_BUCKET_NAME`, `AUTOQA_BUCKET_NAME` (S3 buckets)

### Branch Protection & Code Review

The repository uses GitHub branch protection rules to ensure code quality:

**Protected Branch:** `main`

**Requirements:**
- Pull requests required for all changes
- 1 approval from code owners required
- Status check must pass: `Build Container - WikiDict`
- Linear history enforced
- Force pushes and deletions blocked

**Code Ownership:**
- All code changes require review from `@saurabhmaurya45`
- Defined in `.github/CODEOWNERS`
- Automatic reviewer assignment on PRs

**Pull Request Process:**
1. Create feature branch from `main`
2. Make changes and commit
3. Push branch and create PR using the PR template
4. Wait for CI checks to pass (build, security scans, linting)
5. Get approval from code owner
6. Merge via GitHub UI (squash merge recommended)

## Infrastructure

See [deployment/terraform/README.md](deployment/terraform/README.md) for:
- AWS EKS cluster setup
- Single cluster with namespace-based environments (autoqa, prod)
- Terraform configuration and deployment instructions

## Documentation

### Infrastructure & Architecture
- [Terraform Infrastructure Guide](deployment/terraform/README.md)
- [Architecture Review Board (ARB)](docs/architecture_review_board_arb_read_optimized_dictionary_system.md)
- [Infrastructure Costing & Decisions](docs/infrastructure-costing-decisions.md)

### Learning Experiments
- [Experiments Index](experiments/README.md) - Complete learning path
- [Experiment 01: Local Kubernetes Deployment](experiments/01-local-k8s-deployment/README.md) ✅

## License

MIT
