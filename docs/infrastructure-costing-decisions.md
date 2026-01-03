# Infrastructure Costing & Architecture Decisions

**Project**: SM-WikiDict
**Date**: January 2026
**Budget Constraint**: ₹1,000/month (~$12 USD)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Initial Architecture: AWS EKS](#initial-architecture-aws-eks)
3. [Cost Analysis: The Reality Check](#cost-analysis-the-reality-check)
4. [Cloud Provider Evaluation](#cloud-provider-evaluation)
5. [VPS Provider Comparison](#vps-provider-comparison)
6. [Final Recommendations](#final-recommendations)
7. [Learning Path Strategy](#learning-path-strategy)
8. [Technology Stack](#technology-stack)
9. [Decision Timeline](#decision-timeline)

---

## Executive Summary

### The Challenge
Build a production-grade dictionary service with Kubernetes, CI/CD, and observability on a ₹1,000/month budget while learning industry-standard practices.

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Platform** | Oracle Cloud Free Tier (Primary) or Contabo VPS M (Fallback) |
| **Kubernetes** | K3s instead of managed EKS/GKE |
| **Architecture** | Single cluster with namespace-based environments |
| **Learning Path** | Local development first, cloud deployment later |
| **Cost Target** | ₹0 (Oracle) or ₹815/month (Contabo) |

### Cost Comparison at a Glance

```
AWS EKS:        ₹10,700/month  ❌ 10x over budget
GCP GKE:        ₹7,000/month   ❌ 7x over budget
Oracle Free:    ₹0/month       ✅ Perfect fit
Contabo VPS M:  ₹815/month     ✅ Within budget
Hetzner CX42:   ₹1,270/month   ⚠️  Slightly over
```

---

## Initial Architecture: AWS EKS

### Original Design

**Multi-Environment Approach (Version 1)**
- Separate EKS clusters for each environment (autoqa, pre, prod)
- Dedicated VPCs per environment
- Individual NAT gateways and networking infrastructure

**Optimized Single-Cluster Approach (Version 2)**
- Single EKS cluster with namespace-based environment isolation
- Shared VPC and networking
- Kubernetes namespaces: `autoqa`, `prod`

### Infrastructure Components

```
VPC (10.0.0.0/16)
├── Public Subnets (10.0.1.0/24, 10.0.2.0/24)
│   ├── Internet Gateway
│   └── NAT Gateway (for private subnet internet access)
├── Private Subnets (10.0.11.0/24, 10.0.12.0/24)
│   └── EKS Worker Nodes
└── EKS Control Plane
    ├── Namespace: autoqa
    └── Namespace: prod
```

### Terraform Structure

```
deployment/terraform/
├── infra-setup/           # S3 + DynamoDB for remote state
│   └── main.tf
├── cluster/               # Single EKS cluster configuration
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── backend.tf
└── modules/               # Reusable modules
    ├── vpc/
    ├── eks/
    └── ecr/
```

---

## Cost Analysis: The Reality Check

### AWS EKS Monthly Costs (INR)

| Component | Configuration | Monthly Cost (₹) | Annual Cost (₹) |
|-----------|--------------|------------------|-----------------|
| **EKS Control Plane** | 1 cluster | ₹6,000 | ₹72,000 |
| **NAT Gateway** | 1 NAT (optimized) | ₹2,700 + ₹660 data | ₹40,320 |
| **Worker Nodes** | 2× t3.small (2 vCPU, 2GB) | ₹1,500 | ₹18,000 |
| **EBS Storage** | 40GB gp3 | ₹320 | ₹3,840 |
| **Data Transfer** | Minimal | ₹200 | ₹2,400 |
| **ECR** | Container registry | ₹40 | ₹480 |
| **Total** | | **₹10,700** | **₹128,400** |

### Cost Breakdown Analysis

**The Big Three**
1. **EKS Control Plane**: ₹6,000/month (56% of total)
   - Fixed cost for managed Kubernetes
   - No way to reduce this

2. **NAT Gateway**: ₹3,360/month (31% of total)
   - ₹2,700 fixed + ₹660 for data processing
   - Required for private subnets to reach internet

3. **Worker Nodes**: ₹1,500/month (14% of total)
   - Already using smallest practical instance (t3.small)
   - Could use t3.micro but not recommended for production

### Why AWS Doesn't Work for This Budget

```
Budget:              ₹1,000/month
AWS Minimum Cost:    ₹10,700/month
Gap:                 ₹9,700/month (970% over budget)
```

**Attempted Optimizations**
- ✅ Single cluster instead of multiple → Saved ₹12,000/month
- ✅ Single NAT Gateway → Saved ₹2,700/month
- ✅ Smallest worker nodes (t3.small) → Already at minimum
- ❌ Still 10x over budget

**Reality**: Managed Kubernetes (EKS/GKE/AKS) is designed for businesses spending $500-5,000+/month, not individual learners.

---

## Cloud Provider Evaluation

### 1. Google Cloud Platform (GCP)

#### Option A: GKE Autopilot
```
Cost: ~₹7,000/month
├── Control Plane: ₹6,000/month ($72/month)
├── Compute: ₹800-1,500/month (0.5-1 vCPU)
└── Networking: Minimal
```
**Verdict**: Still 7x over budget ❌

#### Option B: Cloud Run (Serverless)
```
Cost: ~₹150-750/month
├── 1M requests free/month
├── ₹0.30 per 1M requests after
└── Minimal compute charges
```
**Pros**: Extremely cheap for low traffic
**Cons**: Not Kubernetes, can't learn K8s/ArgoCD
**Verdict**: Wrong tool for learning objectives ❌

#### Option C: e2-micro Free Tier
```
Cost: ₹0/month (always free)
├── 0.25-2 vCPU (shared)
├── 1GB RAM
└── 30GB storage
```
**Pros**: Completely free
**Cons**: 1GB RAM too small for K3s + observability stack
**Verdict**: Insufficient resources ❌

### 2. AWS Alternatives

#### AWS Lightsail
```
Cost: ₹2,880/month ($3.50/month = ₹294 × 2 instances)
├── 1GB RAM per instance
├── 1 vCPU
└── 40GB SSD
```
**Verdict**: Need 2 instances minimum, still limited RAM ⚠️

### 3. Oracle Cloud Infrastructure (OCI)

#### Free Tier (Always Free)
```
Cost: ₹0/month FOREVER
├── 4× Arm-based Ampere A1 cores
├── 24GB RAM
├── 200GB Block Storage
├── 10TB/month bandwidth
└── No credit card expiry
```

**Specs Distribution Examples**:
- Option 1: 1 VM with 4 cores + 24GB RAM
- Option 2: 2 VMs with 2 cores + 12GB RAM each
- Option 3: 4 VMs with 1 core + 6GB RAM each

**Pros**:
- ✅ Completely free forever (not trial)
- ✅ 24GB RAM is enough for K3s + full observability stack
- ✅ ARM architecture (good learning experience)
- ✅ Multiple datacodes (Mumbai, Hyderabad available)

**Cons**:
- ⚠️ ARM architecture (need ARM-compatible images)
- ⚠️ Account approval can be strict
- ⚠️ Free tier capacity sometimes unavailable in popular regions

**Verdict**: Best option if account approved ✅

### 4. DigitalOcean

#### DOKS (DigitalOcean Kubernetes Service)
```
Cost: ₹3,200/month ($38/month)
├── Control Plane: Free
├── 2× Droplets (2GB): ₹1,600 each
└── Load Balancer: Included
```
**Verdict**: 3x over budget ❌

---

## VPS Provider Comparison

When managed Kubernetes proved too expensive, we evaluated VPS providers where you can install K3s yourself.

### Contabo (Recommended)

#### VPS M - Best Value
```
Price: ₹815/month (~€9/month)
Location: Singapore datacenter
Specs:
├── 6 vCPU cores
├── 16GB RAM
├── 400GB NVMe SSD
└── 32TB/month bandwidth

Perfect for:
├── K3s cluster
├── ArgoCD
├── Full observability stack (Grafana, Prometheus, Loki)
├── 2-3 environments (autoqa, prod)
└── Room to grow
```

**Pros**:
- ✅ Exceptional value (16GB RAM at ₹815)
- ✅ Singapore datacenter (low latency for India)
- ✅ Generous bandwidth (32TB)
- ✅ NVMe SSD for better performance
- ✅ Within budget

**Cons**:
- ⚠️ Mixed reputation (some report support issues)
- ⚠️ Not Tier-1 infrastructure
- ⚠️ No managed Kubernetes (you maintain everything)

#### VPS L - Maximum Resources
```
Price: ₹1,360/month (~€15/month)
Specs:
├── 8 vCPU cores
├── 30GB RAM
├── 800GB NVMe SSD
└── 32TB/month bandwidth
```

**When to choose**: If you need more RAM for heavier workloads or testing at scale.

### Hetzner Cloud (Premium Alternative)

#### CX42
```
Price: ₹1,270/month (~€15/month)
Location: Germany, Finland, USA (no Asia)
Specs:
├── 8 vCPU cores (dedicated)
├── 16GB RAM
├── 320GB SSD
└── 20TB/month bandwidth
```

**Pros**:
- ✅ Better reputation and reliability
- ✅ Excellent support
- ✅ Dedicated CPU cores (better performance)
- ✅ European data protection standards
- ✅ Great network quality

**Cons**:
- ❌ No Asia/India datacenters (higher latency)
- ⚠️ Slightly over ₹1,000 budget
- ⚠️ Less storage than Contabo

**When to choose**: If reliability and support matter more than cost, and latency to EU/US is acceptable.

### Hostinger VPS

#### KVM 4
```
Price: ₹1,399/month
Location: India, Singapore available
Specs:
├── 8 vCPU cores
├── 16GB RAM
├── 250GB NVMe SSD
└── Unlimited bandwidth
```

**Pros**:
- ✅ Indian company with local support
- ✅ Datacenters in India and Singapore
- ✅ Full root access for K3s installation

**Cons**:
- ⚠️ 40% more expensive than Contabo VPS M
- ⚠️ Over budget at ₹1,399
- ⚠️ Less storage than Contabo

**Verdict**: Good option but Contabo offers better value ⚠️

### Side-by-Side Comparison

| Provider | Plan | Price/mo | vCPU | RAM | Storage | Bandwidth | Location |
|----------|------|----------|------|-----|---------|-----------|----------|
| **Oracle** | Free Tier | ₹0 | 4 ARM | 24GB | 200GB | 10TB | Mumbai, Hyderabad |
| **Contabo** | VPS M | ₹815 | 6 | 16GB | 400GB NVMe | 32TB | Singapore |
| **Contabo** | VPS L | ₹1,360 | 8 | 30GB | 800GB NVMe | 32TB | Singapore |
| **Hetzner** | CX42 | ₹1,270 | 8 | 16GB | 320GB SSD | 20TB | EU/USA |
| **Hostinger** | KVM 4 | ₹1,399 | 8 | 16GB | 250GB NVMe | Unlimited | India, SG |
| AWS EKS | Minimum | ₹10,700 | 4 | 4GB | 40GB | Minimal | Global |

### Resource Requirements Analysis

**For SM-WikiDict with Full Stack**:
```
K3s Control Plane:        ~1GB RAM
K3s Worker (app):         ~1GB RAM
FastAPI app:              ~512MB RAM
Prometheus:               ~2GB RAM
Grafana:                  ~512MB RAM
Loki:                     ~1GB RAM
ArgoCD:                   ~1GB RAM
OTEL Collector:           ~512MB RAM
System overhead:          ~1GB RAM
─────────────────────────────────
Minimum recommended:      ~8GB RAM
Comfortable setup:        16GB RAM
Future-proof:             24GB+ RAM
```

**Storage Requirements**:
```
OS + System:              ~20GB
Docker images:            ~10GB
Prometheus data (30d):    ~20GB
Loki logs (30d):          ~10GB
Application data:         ~10GB
Buffer:                   ~30GB
─────────────────────────────────
Minimum:                  ~100GB
Recommended:              200GB+
```

---

## Final Recommendations

### Recommendation Matrix

| Priority | Choice | Cost | Why |
|----------|--------|------|-----|
| **Learning** | Oracle Free Tier | ₹0 | Free, ARM experience, production-grade resources |
| **Budget** | Contabo VPS M | ₹815 | Best ₹/resource ratio, Singapore location |
| **Reliability** | Hetzner CX42 | ₹1,270 | Better support, dedicated CPU, proven track record |
| **Max Power** | Contabo VPS L | ₹1,360 | 30GB RAM for complex scenarios |

### Decision Tree

```
Start
  │
  ├─→ Can you get Oracle Cloud account?
  │   ├─→ YES: Use Oracle Free Tier (₹0) ✅
  │   └─→ NO: Continue
  │
  ├─→ Is ₹815/month acceptable?
  │   ├─→ YES: Contabo VPS M (₹815) ✅
  │   └─→ NO: Continue
  │
  ├─→ Can you stretch to ₹1,270?
  │   ├─→ YES: Hetzner CX42 (₹1,270) ✅
  │   └─→ NO: Continue
  │
  └─→ Start with local K3s, save up
```

### Action Plan

#### Phase 1: Try Oracle Cloud Free Tier (Week 1)
```bash
1. Sign up for Oracle Cloud
2. Request Always Free tier
3. If approved → Deploy K3s
4. If rejected → Move to Phase 2
```

#### Phase 2: Fallback to Contabo VPS M (Week 2)
```bash
1. Sign up for Contabo
2. Choose VPS M - Singapore datacenter
3. Order with Ubuntu 22.04 LTS
4. Cost: ₹815/month
```

#### Phase 3: Local Learning (Parallel to above)
```bash
# Start immediately, regardless of cloud choice
1. Install K3s locally on MacBook M1
2. Deploy FastAPI app
3. Set up ArgoCD
4. Configure GitHub Actions
5. Add observability stack
6. Test everything locally
7. Then migrate to cloud
```

---

## Learning Path Strategy

### 6-Phase Roadmap

#### Phase 1: Local K3s Setup (Weeks 1-2)
**Environment**: MacBook M1 (8GB RAM)
**Cost**: ₹0

```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Verify
kubectl get nodes

# Deploy app
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

**Learning Outcomes**:
- Kubernetes concepts (Pods, Deployments, Services)
- kubectl commands
- YAML manifests
- Local development workflow

#### Phase 2: GitOps with ArgoCD (Week 3)
**Add**: ArgoCD for continuous deployment

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

**Learning Outcomes**:
- GitOps methodology
- Declarative deployments
- Git as single source of truth
- Automated sync and rollback

#### Phase 3: CI Pipeline with GitHub Actions (Week 4)
**Add**: Automated build and push

```yaml
# .github/workflows/ci.yaml
name: CI Pipeline
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
      - name: Push to GHCR
        run: docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
```

**Learning Outcomes**:
- GitHub Actions workflows
- Container registry (GHCR)
- Image tagging strategies
- CI/CD integration

#### Phase 4: Observability Stack (Weeks 5-6)
**Add**: Prometheus, Grafana, Loki, OTEL

```bash
# Install using Helm
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts

helm install prometheus prometheus-community/kube-prometheus-stack

# Install Loki
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack
```

**Learning Outcomes**:
- Metrics collection (Prometheus)
- Visualization (Grafana)
- Log aggregation (Loki)
- Distributed tracing (Jaeger)
- OpenTelemetry instrumentation

#### Phase 5: Alerting (Week 7)
**Add**: Slack/Teams webhook alerting

```yaml
# Alertmanager config
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#alerts'
        text: 'Alert: {{ .CommonLabels.alertname }}'
```

**Learning Outcomes**:
- Alert rules and thresholds
- Notification channels
- On-call practices
- Incident response

#### Phase 6: Cloud Deployment (Week 8+)
**Deploy**: Move to Oracle Cloud or Contabo

```bash
# Provision VPS
terraform apply

# Install K3s
curl -sfL https://get.k3s.io | sh -

# Migrate workloads
kubectl config use-context production
kubectl apply -f k8s/
```

**Learning Outcomes**:
- Cloud infrastructure
- Production deployment
- Migration strategies
- DNS and ingress configuration

### Time Investment

| Phase | Duration | Daily Hours | Effort Level |
|-------|----------|-------------|--------------|
| Phase 1 | 2 weeks | 2-3 hours | Medium |
| Phase 2 | 1 week | 2 hours | Medium |
| Phase 3 | 1 week | 1-2 hours | Low |
| Phase 4 | 2 weeks | 3-4 hours | High |
| Phase 5 | 1 week | 1-2 hours | Low |
| Phase 6 | 1+ week | 2-3 hours | Medium |
| **Total** | **8+ weeks** | **15-20 hrs/week** | |

---

## Technology Stack

### Application Layer
```
FastAPI (Python 3.11+)
├── Uvicorn (ASGI server)
├── Pydantic (data validation)
└── Python 3.11-slim Docker image
```

### Infrastructure Layer
```
Kubernetes (K3s)
├── Lightweight K8s distribution
├── Single binary installation
├── Built-in containerd
└── Perfect for edge/learning
```

### CI/CD Layer
```
GitHub Actions
├── Docker build and push
├── Automated testing
├── Version tagging
└── GHCR integration

ArgoCD
├── GitOps continuous delivery
├── Automatic sync from Git
├── Declarative deployments
└── Self-healing applications
```

### Observability Layer
```
Metrics
├── Prometheus (collection & storage)
├── Grafana (visualization)
└── AlertManager (notifications)

Logs
├── Loki (log aggregation)
└── Promtail (log shipping)

Traces
├── OpenTelemetry (instrumentation)
├── Jaeger (distributed tracing)
└── OTEL Collector (processing)
```

### Storage Layer
```
Application
├── Wikipedia data (S3/GCS)
├── In-memory index (~50MB)
└── Byte-range HTTP reads

Metrics/Logs
├── Prometheus TSDB (local)
├── Loki (local chunks)
└── Optional: S3 for long-term storage
```

---

## Decision Timeline

### Week 0: Initial Planning
- ✅ Decided on Terraform for IaC
- ✅ Chose AWS EKS initially
- ✅ Created multi-environment structure

### Week 0.5: Architecture Pivot
- ✅ Simplified to single cluster
- ✅ Namespace-based environments
- ✅ Deleted unnecessary modules

### Week 1: Reality Check
- ✅ Calculated AWS costs: ₹10,700/month
- ❌ Realized 10x over budget
- ✅ Explored GCP alternatives
- ❌ Still too expensive

### Week 1.5: Alternative Research
- ✅ Discovered Oracle Cloud Free Tier
- ✅ Evaluated VPS providers
- ✅ Compared Contabo, Hetzner, Hostinger
- ✅ Defined learning path strategy

### Current Status
```
Decision: Oracle Cloud Free Tier (primary) or Contabo VPS M (fallback)
Cost: ₹0 or ₹815/month
Approach: Local K3s first, cloud deployment later
Timeline: 8+ weeks to complete full stack
```

---

## Cost Savings Analysis

### What We Saved

| Item | Original | Optimized | Savings |
|------|----------|-----------|---------|
| Multi-cluster to single | ₹32,100 | ₹10,700 | ₹21,400/mo |
| Multiple NATs to one | ₹13,440 | ₹3,360 | ₹10,080/mo |
| AWS to Oracle Free | ₹10,700 | ₹0 | ₹10,700/mo |
| **Total Annual Savings** | | | **₹505,080** |

### ROI on Learning Investment

**If you were paying for AWS EKS**:
```
Annual cost: ₹128,400
With Oracle Free Tier: ₹0
Savings: ₹128,400/year

That's equivalent to:
- 10.7 months of your ₹12,000 salary
- 157 Contabo VPS M months
- 128 months of your ₹1,000 budget
```

**Learning Value**:
```
Skills gained:
├── Kubernetes (K3s) → Market value: ₹8-15 LPA
├── ArgoCD/GitOps → Market value: ₹10-18 LPA
├── Observability → Market value: ₹12-20 LPA
├── Terraform/IaC → Market value: ₹8-15 LPA
└── Cloud Architecture → Market value: ₹15-25 LPA

Combined skill set: ₹15-25 LPA DevOps/SRE role
Investment: ₹0-815/month for 2-3 months
ROI: Infinite (if using Oracle) or 1800%+ (if using Contabo)
```

---

## Key Takeaways

### 1. Managed Kubernetes ≠ Budget Friendly
- EKS/GKE/AKS are for businesses with $500+/month budgets
- Control plane alone costs ₹6,000/month
- Not suitable for individual learning projects

### 2. Free Tiers Can Be Production-Grade
- Oracle Cloud Free Tier offers 24GB RAM permanently
- More resources than many paid options
- ARM architecture is valuable learning experience

### 3. VPS + K3s = Budget Kubernetes
- Full control, fraction of the cost
- Learn more by managing everything yourself
- Contabo VPS M at ₹815 is exceptional value

### 4. Learn Locally First
- No need to pay for cloud while learning basics
- M1 Mac with 8GB RAM can run K3s comfortably
- Migrate to cloud only when production-ready

### 5. Total Cost of Ownership
```
AWS EKS:
├── Infrastructure: ₹10,700/month
├── Learning time: Moderate (managed service)
└── Annual: ₹128,400

Oracle Free:
├── Infrastructure: ₹0/month
├── Learning time: Higher (self-managed)
└── Annual: ₹0

Contabo VPS M:
├── Infrastructure: ₹815/month
├── Learning time: Higher (self-managed)
└── Annual: ₹9,780

Winner: Oracle Free Tier (₹0) or Contabo (₹9,780 vs ₹128,400)
Savings: ₹118,620/year with Contabo
```

---

## Next Steps

### Immediate Actions (This Week)

1. **Try Oracle Cloud**
   ```bash
   # Sign up
   https://signup.cloud.oracle.com/

   # Choose Mumbai or Hyderabad region
   # Request Always Free tier
   # Wait for approval (1-3 days)
   ```

2. **Local K3s Setup** (Start immediately)
   ```bash
   # Install K3s on MacBook
   curl -sfL https://get.k3s.io | sh -

   # Verify
   kubectl get nodes
   ```

3. **FastAPI Containerization**
   ```bash
   # Build Docker image
   docker build -t sm-wikidict:local .

   # Test locally
   docker run -p 8000:8000 sm-wikidict:local
   ```

### Short Term (Weeks 2-4)

1. Deploy FastAPI to local K3s
2. Set up GitHub Actions CI pipeline
3. Install ArgoCD
4. Configure GitOps workflow

### Medium Term (Weeks 5-8)

1. Add Prometheus + Grafana
2. Integrate OpenTelemetry
3. Set up Loki for logs
4. Configure alerting

### Long Term (Week 8+)

1. Deploy to Oracle Cloud or Contabo
2. Configure production DNS
3. Set up SSL/TLS certificates
4. Implement monitoring dashboards
5. Document everything learned

---

## Conclusion

Starting with grand plans for AWS EKS, we discovered that cloud costs can quickly spiral beyond reach for individual learners. Through systematic evaluation of alternatives, we found that:

1. **Oracle Cloud Free Tier** offers production-grade resources at ₹0 cost
2. **Contabo VPS M** provides exceptional value at ₹815/month as a fallback
3. **Local K3s** enables complete learning without any cloud costs
4. **Managed Kubernetes** is a luxury, not a necessity for learning

The best approach combines:
- Local development with K3s (immediate start, ₹0 cost)
- Oracle Cloud Free Tier for production (₹0 if approved)
- Contabo VPS M as fallback (₹815, still well under budget)

**Total learning investment**: ₹0-815/month for 2-3 months to gain skills worth ₹15-25 LPA in the job market.

**Budget constraint transformed into opportunity**: Learning to build with constraints makes you a better engineer.

---

## References

### Cost Calculators Used
- AWS Pricing Calculator: https://calculator.aws/
- GCP Pricing Calculator: https://cloud.google.com/products/calculator
- Oracle Cloud Pricing: https://www.oracle.com/cloud/price-list/

### Provider Websites
- Oracle Cloud: https://www.oracle.com/cloud/free/
- Contabo: https://contabo.com/en/vps/
- Hetzner: https://www.hetzner.com/cloud
- Hostinger: https://www.hostinger.in/vps-hosting

### Tools & Technologies
- K3s Documentation: https://docs.k3s.io/
- ArgoCD: https://argo-cd.readthedocs.io/
- Prometheus: https://prometheus.io/docs/
- Grafana: https://grafana.com/docs/
- OpenTelemetry: https://opentelemetry.io/docs/

---

**Document Version**: 1.0
**Last Updated**: January 2026
**Status**: Active Decision Document
**Owner**: SM-WikiDict Project Team
