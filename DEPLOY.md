# Fly.io Deployment Guide - Aeon Cascade

Simple single-container deployment for Aeon Cascade on Fly.io.

## Prerequisites

1. **Install flyctl**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login to Fly.io**
   ```bash
   flyctl auth login
   ```

## Initial Setup

1. **Create the app** (first time only)
   ```bash
   cd /Users/noot/Documents/digitalme
   flyctl launch --no-deploy
   ```

   When prompted:
   - App name: `aeon-cascade` (or your preferred name)
   - Region: Choose closest to you (e.g., `iad` for US East)
   - Don't add databases yet
   - Don't deploy yet

2. **Set AWS secrets** (required for INDRA agent)
   ```bash
   flyctl secrets set \
     AWS_ACCESS_KEY_ID="your-aws-access-key" \
     AWS_SECRET_ACCESS_KEY="your-aws-secret-key" \
     AWS_REGION="us-east-1"
   ```

## Deploy

Deploy your application:

```bash
flyctl deploy --dockerfile Dockerfile.fly
```

This will:
- Build both frontend (SvelteKit) and backend (FastAPI)
- Package them in a single container
- Deploy to Fly.io
- Allocate a public URL

## Check Status

```bash
# View app status
flyctl status

# View logs
flyctl logs

# Open in browser
flyctl open
```

## Configuration

The deployment uses:
- **Frontend**: Port 3000 (SvelteKit)
- **Backend**: Port 8000 (FastAPI)
- **Public URL**: Routes to frontend on port 3000
- **Memory**: 1GB RAM (adjust in fly.toml if needed)
- **Auto-scaling**: Enabled (min 0, scales on demand)

## Environment Variables

Set additional environment variables:

```bash
flyctl secrets set KEY=value
```

Common variables:
- `AWS_ACCESS_KEY_ID` - AWS Bedrock access
- `AWS_SECRET_ACCESS_KEY` - AWS Bedrock secret
- `AWS_REGION` - AWS region (default: us-east-1)
- `INDRA_BASE_URL` - INDRA API endpoint (default: https://db.indra.bio)

## Scaling

### Vertical Scaling (More Resources)

Edit `fly.toml` and redeploy:

```toml
[[vm]]
  cpu_kind = "shared"
  cpus = 2          # Increase CPUs
  memory_mb = 2048  # Increase RAM
```

Then redeploy:
```bash
flyctl deploy
```

### Horizontal Scaling (More Instances)

```bash
flyctl scale count 2
```

## Troubleshooting

### View Logs
```bash
# Tail logs
flyctl logs

# Specific timeframe
flyctl logs --region iad
```

### SSH into Container
```bash
flyctl ssh console
```

### Check Backend Health
```bash
curl https://your-app.fly.dev/api/v1/health
```

### Common Issues

**Build fails**:
- Check AWS credentials are set
- Verify frontend builds locally: `cd frontend && npm run build`
- Verify backend installs locally: `pip install -e .`

**Backend not responding**:
- Check logs for Python errors
- Verify AWS Bedrock access from Fly.io region
- Check port 8000 is accessible

**Frontend not responding**:
- Verify build succeeded
- Check SvelteKit adapter is configured
- Check port 3000 is accessible

## Cost Optimization

Fly.io free tier includes:
- Up to 3 shared-cpu-1x 256mb VMs
- 160GB outbound data transfer

To minimize costs:
- Use `auto_stop_machines = true` (already configured)
- Keep `min_machines_running = 0` (scales to zero when idle)
- Monitor usage: `flyctl dashboard`

## Updating

Deploy updates:

```bash
# After making code changes
git add .
git commit -m "Update message"
flyctl deploy
```

## Cleanup

Destroy the app (if needed):

```bash
flyctl apps destroy aeon-cascade
```

## Production Checklist

- [ ] Set AWS credentials as secrets
- [ ] Configure custom domain (optional)
- [ ] Set up monitoring/alerts
- [ ] Test all API endpoints
- [ ] Verify frontend loads correctly
- [ ] Check CORS configuration if needed
- [ ] Review security settings
- [ ] Enable automatic backups (if using databases)

## Architecture

```
┌─────────────────────────────────────┐
│         Fly.io Container            │
│                                     │
│  ┌─────────────┐  ┌──────────────┐ │
│  │  SvelteKit  │  │   FastAPI    │ │
│  │  (Port 3000)│  │  (Port 8000) │ │
│  │             │  │              │ │
│  │  Frontend   │─▶│  Backend     │ │
│  │  Static     │  │  INDRA Agent │ │
│  └─────────────┘  └──────────────┘ │
│                                     │
└─────────────────────────────────────┘
           │
           ▼
    Public Internet
    your-app.fly.dev
```

## Support

- Fly.io Docs: https://fly.io/docs/
- Fly.io Community: https://community.fly.io/
- Check logs: `flyctl logs`
