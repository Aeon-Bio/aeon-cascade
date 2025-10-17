# Azure Deployment Guide for Vibecoding Nights Bot

This guide walks you through deploying the Vibecoding Nights Telegram bot to Azure using Azure Container Instances (ACI) and Azure Container Registry (ACR).

## Prerequisites

### 1. Azure CLI Setup
```bash
# Install Azure CLI (if not already installed)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login
```

You'll need:
- Azure subscription ID
- Resource group name (will be created if it doesn't exist)
- Azure region (e.g., `eastus`, `westeurope`)

### 2. Docker Setup
Ensure Docker is installed and running on your machine.

### 3. Required Information
Before deployment, gather:
- **Telegram Bot Token**: Get from [@BotFather](https://t.me/BotFather)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/)
- **Azure Subscription ID**: Find in Azure Portal or run `az account show --query id -o tsv`

## Configuration

### 1. Update Azure Configuration
Edit `config/config.env` and update the Azure-related variables:

```bash
# Azure Deployment Configuration
AZURE_SUBSCRIPTION_ID=your-subscription-id-here
AZURE_RESOURCE_GROUP=vibecoding-rg           # Resource group name
AZURE_LOCATION=eastus                        # Azure region
ACR_NAME=frontiertower                       # Container registry name (without .azurecr.io)
ACI_NAME=vibecoding-bot                      # Container instance name
KEY_VAULT_NAME=vibecoding-kv                 # Key Vault name (must be globally unique)
MONGODB_ACI_NAME=vibecoding-mongodb          # MongoDB container instance name
VNET_NAME=vibecoding-vnet                    # Virtual network name
SUBNET_NAME=vibecoding-subnet                # Subnet name
```

### 2. Verify Bot Configuration
Make sure your `config/config.yml` has the right settings:
- Leave `telegram_token` and `openai_api_key` as placeholders (they'll be stored in Azure Key Vault)
- Configure `allowed_telegram_usernames` if you want to restrict access

## Deployment

### Quick Deployment
```bash
# Make sure you're in the project root directory
./deploy-azure.sh
```

The script will:
1. 🐳 Create ACR and push Docker image
2. 🌐 Set up Virtual Network and subnet
3. 🔐 Store secrets in Azure Key Vault
4. 🗄️ Deploy MongoDB container instance
5. 🚀 Deploy bot container instance
6. 📋 Configure networking and security

### Step-by-Step Deployment

If you prefer manual control, you can run individual steps:

```bash
# 1. Create resource group
az group create --name vibecoding-rg --location eastus

# 2. Create container registry
az acr create --resource-group vibecoding-rg --name frontiertower --sku Basic

# 3. Build and push Docker image
az acr build --registry frontiertower --image vibecoding-bot:latest .

# 4. Create Key Vault
az keyvault create --name vibecoding-kv --resource-group vibecoding-rg --location eastus

# 5. Store secrets
az keyvault secret set --vault-name vibecoding-kv --name telegram-token --value "YOUR_TOKEN"
az keyvault secret set --vault-name vibecoding-kv --name openai-api-key --value "YOUR_API_KEY"

# 6. Create virtual network
az network vnet create \
  --resource-group vibecoding-rg \
  --name vibecoding-vnet \
  --address-prefix 10.0.0.0/16 \
  --subnet-name vibecoding-subnet \
  --subnet-prefix 10.0.1.0/24

# 7. Deploy MongoDB container
az container create \
  --resource-group vibecoding-rg \
  --name vibecoding-mongodb \
  --image mongo:7.0 \
  --vnet vibecoding-vnet \
  --subnet vibecoding-subnet \
  --ports 27017 \
  --environment-variables MONGO_INITDB_DATABASE=vibecoding_bot \
  --secure-environment-variables MONGO_INITDB_ROOT_USERNAME=admin MONGO_INITDB_ROOT_PASSWORD=vibecoding2024

# 8. Deploy bot container
az container create \
  --resource-group vibecoding-rg \
  --name vibecoding-bot \
  --image frontiertower.azurecr.io/vibecoding-bot:latest \
  --registry-login-server frontiertower.azurecr.io \
  --vnet vibecoding-vnet \
  --subnet vibecoding-subnet \
  --environment-variables PYTHONUNBUFFERED=1 \
  --secure-environment-variables TELEGRAM_TOKEN=@Microsoft.KeyVault(SecretUri=https://vibecoding-kv.vault.azure.net/secrets/telegram-token/) \
  --restart-policy Always
```

## Post-Deployment

### Verify Deployment
```bash
# Check container status
az container show --resource-group vibecoding-rg --name vibecoding-bot --query instanceView.state

# View logs
az container logs --resource-group vibecoding-rg --name vibecoding-bot

# Stream logs in real-time
az container logs --resource-group vibecoding-rg --name vibecoding-bot --follow
```

### Test the Bot
1. Send a message to your bot on Telegram
2. Try the `/start` command
3. Test different chat modes with `/mode`

## Monitoring and Management

### Azure Monitor Logs
- Logs are automatically collected by Azure Monitor
- View logs in Azure Portal under Container Instances
- Stream logs: `az container logs --resource-group vibecoding-rg --name vibecoding-bot --follow`

### Scaling
```bash
# Restart container (Azure Container Instances auto-restart on failure)
az container restart --resource-group vibecoding-rg --name vibecoding-bot

# Update container with new image
az container create \
  --resource-group vibecoding-rg \
  --name vibecoding-bot \
  --image frontiertower.azurecr.io/vibecoding-bot:latest \
  --registry-login-server frontiertower.azurecr.io \
  --vnet vibecoding-vnet \
  --subnet vibecoding-subnet
```

### Updates
```bash
# Rebuild and push new image
az acr build --registry frontiertower --image vibecoding-bot:latest .

# Update container instance
az container delete --resource-group vibecoding-rg --name vibecoding-bot --yes
az container create \
  --resource-group vibecoding-rg \
  --name vibecoding-bot \
  --image frontiertower.azurecr.io/vibecoding-bot:latest \
  --registry-login-server frontiertower.azurecr.io \
  --vnet vibecoding-vnet \
  --subnet vibecoding-subnet \
  --restart-policy Always
```

## Cost Optimization

### Azure Container Instances Pricing
- **CPU**: ~$0.0012 per vCPU per second
- **Memory**: ~$0.00016 per GB per second
- **Example**: 1 vCPU + 1.5GB RAM = ~$25-30/month (running 24/7)

### Cost-Saving Tips
1. **Right-size resources**: Start with minimal CPU/memory (0.5 vCPU, 1GB RAM)
2. **Use Azure Reserved Instances**: For long-term deployments
3. **Monitor usage**: Use Azure Cost Management
4. **Consider Azure Container Apps**: For more advanced scaling scenarios

## Troubleshooting

### Common Issues

**Bot not responding:**
```bash
# Check container status
az container show --resource-group vibecoding-rg --name vibecoding-bot

# Check logs for errors
az container logs --resource-group vibecoding-rg --name vibecoding-bot
```

**Secret access issues:**
```bash
# Verify Key Vault exists and secrets are set
az keyvault secret list --vault-name vibecoding-kv

# Test secret access
az keyvault secret show --vault-name vibecoding-kv --name telegram-token
```

**Network connectivity:**
```bash
# Check virtual network configuration
az network vnet show --resource-group vibecoding-rg --name vibecoding-vnet

# Check subnet configuration
az network vnet subnet show --resource-group vibecoding-rg --vnet-name vibecoding-vnet --name vibecoding-subnet
```

**Container registry issues:**
```bash
# Check ACR login
az acr login --name frontiertower

# List images in registry
az acr repository list --name frontiertower
```

### Logs Analysis
```bash
# Get recent logs
az container logs --resource-group vibecoding-rg --name vibecoding-bot --tail 100

# Stream logs in real-time
az container logs --resource-group vibecoding-rg --name vibecoding-bot --follow

# Check MongoDB logs
az container logs --resource-group vibecoding-rg --name vibecoding-mongodb
```

## Database Options

### Option 1: MongoDB on ACI (Current)
- Uses MongoDB container instance
- Data stored on Azure File Share for persistence
- Good for development and small-scale production

### Option 2: Azure Cosmos DB (Recommended for Production)
```bash
# Create Cosmos DB account with MongoDB API
az cosmosdb create \
  --resource-group vibecoding-rg \
  --name vibecoding-cosmosdb \
  --kind MongoDB \
  --server-version 4.2 \
  --default-consistency-level Eventual

# Get connection string
az cosmosdb keys list --resource-group vibecoding-rg --name vibecoding-cosmosdb --type connection-strings
```

### Option 3: MongoDB Atlas
- Fully managed MongoDB service
- Update `MONGODB_URI` in Key Vault with Atlas connection string

## Security Best Practices

1. **Secrets Management**: All sensitive data stored in Azure Key Vault
2. **Network Security**: Virtual Network with private subnets
3. **Identity Management**: Managed identities for container access
4. **Encryption**: Secrets and data encrypted at rest and in transit
5. **Access Control**: Azure RBAC for resource access

## Advanced Configuration

### Using Azure Container Apps (Alternative)
For more advanced scenarios, consider Azure Container Apps:

```bash
# Create Container Apps environment
az containerapp env create \
  --name vibecoding-env \
  --resource-group vibecoding-rg \
  --location eastus

# Deploy with Container Apps
az containerapp create \
  --name vibecoding-bot \
  --resource-group vibecoding-rg \
  --environment vibecoding-env \
  --image frontiertower.azurecr.io/vibecoding-bot:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3
```

### Persistent Storage
```bash
# Create storage account for persistent data
az storage account create \
  --name vibecodingstorage \
  --resource-group vibecoding-rg \
  --location eastus \
  --sku Standard_LRS

# Create file share for MongoDB data
az storage share create \
  --name mongodb-data \
  --account-name vibecodingstorage
```

## Cleanup

To remove all Azure resources:
```bash
cd azure/
./cleanup-azure.sh
```

This will delete:
- Resource group and all contained resources
- Container instances
- Container registry
- Key Vault
- Virtual network
- Storage accounts

**Note**: This will permanently delete all data. Make sure to backup any important information first.

## Support

For issues:
1. Check the troubleshooting section above
2. Review Azure Monitor logs
3. Verify Azure permissions and configuration
4. Check the main project README for general bot issues

## Migration from AWS

If migrating from AWS:
1. Export your data from AWS (MongoDB, secrets)
2. Update configuration files for Azure
3. Run the Azure deployment script
4. Import your data to Azure services
5. Update DNS/webhook URLs if applicable
6. Test thoroughly before decommissioning AWS resources
