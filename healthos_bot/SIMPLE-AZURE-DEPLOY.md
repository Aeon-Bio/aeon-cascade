# Simple Azure Deployment - 5 Minutes Setup

The **absolute simplest** way to deploy your Telegram bot to Azure. No persistent storage, no complex networking - just get it running fast.

## Prerequisites

1. **Azure CLI installed**:
   ```bash
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   ```

2. **Login to Azure**:
   ```bash
   az login
   ```

3. **Your tokens ready**:
   - Telegram Bot Token (from @BotFather)
   - OpenAI API Key

## 5-Minute Deployment

### Step 1: Set Variables
```bash
# Set your values here
RESOURCE_GROUP="my-bot-rg"
LOCATION="eastus"
BOT_NAME="my-telegram-bot"
TELEGRAM_TOKEN="your-telegram-token-here"
OPENAI_API_KEY="your-openai-key-here"
```

### Step 2: Create Resource Group
```bash
az group create --name $RESOURCE_GROUP --location $LOCATION
```

### Step 3: Deploy Container (All-in-One)
```bash
az container create \
  --resource-group $RESOURCE_GROUP \
  --name $BOT_NAME \
  --image frontiertower.azurecr.io/vibecoding-bot:latest \
  --cpu 1 \
  --memory 1 \
  --restart-policy Always \
  --environment-variables \
    PYTHONUNBUFFERED=1 \
  --secure-environment-variables \
    TELEGRAM_TOKEN="$TELEGRAM_TOKEN" \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    MONGODB_URI="mongodb://localhost:27017/vibecoding_bot"
```

**That's it!** Your bot is now running on Azure.

## Check Status

```bash
# Check if container is running
az container show --resource-group $RESOURCE_GROUP --name $BOT_NAME --query instanceView.state

# View logs
az container logs --resource-group $RESOURCE_GROUP --name $BOT_NAME

# Stream logs in real-time
az container logs --resource-group $RESOURCE_GROUP --name $BOT_NAME --follow
```

## Update Bot

```bash
# Restart with new image
az container restart --resource-group $RESOURCE_GROUP --name $BOT_NAME
```

## Delete Everything

```bash
# Remove all resources
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

## Cost

- **~$25-30/month** for 1 vCPU, 1GB RAM running 24/7
- **Pay-per-second** billing

## Limitations of Simple Setup

- ❌ **No persistent data** - Bot memory resets on restart
- ❌ **No database** - Can't store user conversations
- ❌ **No custom networking** - Uses default Azure networking
- ✅ **Bot works perfectly** for basic chat functionality
- ✅ **Extremely simple** to deploy and manage

## Upgrade Later

When you need persistence, run the full deployment:
```bash
./deploy-azure.sh
```

This simple setup gets you started in 5 minutes with zero complexity!
