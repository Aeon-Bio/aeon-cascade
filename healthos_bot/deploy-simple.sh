#!/bin/bash

# Simple Azure Deployment - One Command Setup
# No persistent storage, no complex networking - just deploy fast!

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Simple Azure Bot Deployment${NC}"
echo -e "${BLUE}================================${NC}"
echo

# Get user inputs
read -p "Enter your Telegram Bot Token: " -s TELEGRAM_TOKEN
echo
read -p "Enter your OpenAI API Key: " -s OPENAI_API_KEY
echo
read -p "Enter Resource Group name (default: my-bot-rg): " RESOURCE_GROUP
RESOURCE_GROUP=${RESOURCE_GROUP:-"my-bot-rg"}

read -p "Enter Azure location (default: eastus): " LOCATION
LOCATION=${LOCATION:-"eastus"}

read -p "Enter bot name (default: my-telegram-bot): " BOT_NAME
BOT_NAME=${BOT_NAME:-"my-telegram-bot"}

echo
echo -e "${YELLOW}Deploying with:${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "Bot Name: $BOT_NAME"
echo

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first:"
    echo "curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo "❌ Not logged into Azure. Please run: az login"
    exit 1
fi

echo -e "${BLUE}Step 1: Creating resource group...${NC}"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo -e "${BLUE}Step 2: Deploying container...${NC}"
az container create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$BOT_NAME" \
  --image frontiertower.azurecr.io/vibecoding-bot:latest \
  --cpu 1 \
  --memory 1 \
  --restart-policy Always \
  --environment-variables \
    PYTHONUNBUFFERED=1 \
  --secure-environment-variables \
    TELEGRAM_TOKEN="$TELEGRAM_TOKEN" \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    MONGODB_URI="mongodb://localhost:27017/vibecoding_bot" \
  --output none

echo
echo -e "${GREEN}✅ Bot deployed successfully!${NC}"
echo
echo -e "${YELLOW}Useful commands:${NC}"
echo "Check status: az container show --resource-group $RESOURCE_GROUP --name $BOT_NAME --query instanceView.state"
echo "View logs: az container logs --resource-group $RESOURCE_GROUP --name $BOT_NAME"
echo "Stream logs: az container logs --resource-group $RESOURCE_GROUP --name $BOT_NAME --follow"
echo "Delete all: az group delete --name $RESOURCE_GROUP --yes --no-wait"
echo
echo -e "${GREEN}🎉 Your bot is now running on Azure!${NC}"
echo "Test it by sending a message to your Telegram bot."
