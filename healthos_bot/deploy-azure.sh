#!/bin/bash

# Vibecoding Nights Bot - Azure Deployment Script
# This script deploys the Telegram bot to Azure using Container Instances and Container Registry

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running from project root
if [ ! -f "docker-compose.yml" ]; then
    log_error "Please run this script from the project root directory"
    exit 1
fi

# Load configuration
if [ -f "config/config.env" ]; then
    source config/config.env
    log_info "Loaded configuration from config/config.env"
else
    log_error "config/config.env not found"
    exit 1
fi

# Set default values if not provided
AZURE_RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-"vibecoding-rg"}
AZURE_LOCATION=${AZURE_LOCATION:-"eastus"}
ACR_NAME=${ACR_NAME:-"frontiertower"}
ACI_NAME=${ACI_NAME:-"vibecoding-bot"}
KEY_VAULT_NAME=${KEY_VAULT_NAME:-"vibecoding-kv-$(date +%s)"}  # Add timestamp for uniqueness
MONGODB_ACI_NAME=${MONGODB_ACI_NAME:-"vibecoding-mongodb"}
VNET_NAME=${VNET_NAME:-"vibecoding-vnet"}
SUBNET_NAME=${SUBNET_NAME:-"vibecoding-subnet"}
STORAGE_ACCOUNT_NAME=${STORAGE_ACCOUNT_NAME:-"vibecodingstorage$(date +%s)"}

# Validate required environment variables
required_vars=(
    "AZURE_SUBSCRIPTION_ID"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        log_error "Required environment variable $var is not set"
        exit 1
    fi
done

# Check Azure CLI installation and authentication
if ! command -v az &> /dev/null; then
    log_error "Azure CLI is not installed. Please install it first."
    exit 1
fi

if ! az account show &> /dev/null; then
    log_error "Azure CLI not authenticated. Please run 'az login' first."
    exit 1
fi

# Set subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
log_info "Using Azure subscription: $AZURE_SUBSCRIPTION_ID"

log_info "Starting deployment to Azure region: $AZURE_LOCATION"

# Step 1: Create Resource Group
log_info "Creating resource group..."
if ! az group show --name "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION"
    log_success "Resource group created: $AZURE_RESOURCE_GROUP"
else
    log_info "Resource group already exists: $AZURE_RESOURCE_GROUP"
fi

# Step 2: Create Container Registry
log_info "Setting up Azure Container Registry..."
if ! az acr show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    log_info "Creating ACR: $ACR_NAME"
    az acr create \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku Basic \
        --admin-enabled true
    log_success "ACR created successfully"
else
    log_info "ACR already exists: $ACR_NAME"
fi

# Step 3: Build and push Docker image
log_info "Building and pushing Docker image..."
ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"

# Login to ACR
az acr login --name "$ACR_NAME"

# Build and push image using ACR build (more efficient)
log_info "Building Docker image in ACR..."
az acr build \
    --registry "$ACR_NAME" \
    --image "vibecoding-bot:latest" \
    --image "vibecoding-bot:$(date +%Y%m%d-%H%M%S)" \
    .

log_success "Docker image built and pushed successfully"

# Step 4: Create Key Vault
log_info "Setting up Azure Key Vault..."
if ! az keyvault show --name "$KEY_VAULT_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    log_info "Creating Key Vault: $KEY_VAULT_NAME"
    az keyvault create \
        --name "$KEY_VAULT_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --location "$AZURE_LOCATION" \
        --sku standard
    log_success "Key Vault created successfully"
else
    log_info "Key Vault already exists: $KEY_VAULT_NAME"
fi

# Step 5: Store secrets in Azure Key Vault
log_info "Setting up secrets in Azure Key Vault..."

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$secret_name" &> /dev/null; then
        log_info "Updating existing secret: $secret_name"
        az keyvault secret set \
            --vault-name "$KEY_VAULT_NAME" \
            --name "$secret_name" \
            --value "$secret_value"
    else
        log_info "Creating new secret: $secret_name"
        az keyvault secret set \
            --vault-name "$KEY_VAULT_NAME" \
            --name "$secret_name" \
            --value "$secret_value"
    fi
}

# You'll need to provide these values
read -p "Enter your Telegram Bot Token: " -s TELEGRAM_TOKEN
echo
read -p "Enter your OpenAI API Key: " -s OPENAI_API_KEY
echo
read -p "Enter your MongoDB URI (or press Enter to use ACI MongoDB): " MONGODB_URI
echo

if [ -z "$MONGODB_URI" ]; then
    MONGODB_URI="mongodb://admin:vibecoding2024@$MONGODB_ACI_NAME.${AZURE_LOCATION}.azurecontainer.io:27017/vibecoding_bot?authSource=admin"
fi

create_or_update_secret "telegram-token" "$TELEGRAM_TOKEN"
create_or_update_secret "openai-api-key" "$OPENAI_API_KEY"
create_or_update_secret "mongodb-uri" "$MONGODB_URI"
create_or_update_secret "mongo-root-username" "admin"
create_or_update_secret "mongo-root-password" "vibecoding2024"

log_success "Secrets configured successfully"

# Step 6: Create Virtual Network
log_info "Setting up Virtual Network..."
if ! az network vnet show --resource-group "$AZURE_RESOURCE_GROUP" --name "$VNET_NAME" &> /dev/null; then
    log_info "Creating Virtual Network: $VNET_NAME"
    az network vnet create \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --name "$VNET_NAME" \
        --address-prefix 10.0.0.0/16 \
        --subnet-name "$SUBNET_NAME" \
        --subnet-prefix 10.0.1.0/24
    log_success "Virtual Network created successfully"
else
    log_info "Virtual Network already exists: $VNET_NAME"
fi

# Step 7: Create Storage Account for persistent data
log_info "Setting up Storage Account for persistent data..."
if ! az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    log_info "Creating Storage Account: $STORAGE_ACCOUNT_NAME"
    az storage account create \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --location "$AZURE_LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2
    log_success "Storage Account created successfully"
else
    log_info "Storage Account already exists: $STORAGE_ACCOUNT_NAME"
fi

# Create file share for MongoDB data
log_info "Creating file share for MongoDB data..."
STORAGE_KEY=$(az storage account keys list --resource-group "$AZURE_RESOURCE_GROUP" --account-name "$STORAGE_ACCOUNT_NAME" --query '[0].value' -o tsv)

if ! az storage share show --name "mongodb-data" --account-name "$STORAGE_ACCOUNT_NAME" --account-key "$STORAGE_KEY" &> /dev/null; then
    az storage share create \
        --name "mongodb-data" \
        --account-name "$STORAGE_ACCOUNT_NAME" \
        --account-key "$STORAGE_KEY" \
        --quota 10
    log_success "File share created for MongoDB data"
else
    log_info "File share already exists for MongoDB data"
fi

# Step 8: Deploy MongoDB Container Instance
log_info "Deploying MongoDB container instance..."

# Check if MongoDB container already exists
if az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$MONGODB_ACI_NAME" &> /dev/null; then
    log_info "MongoDB container already exists, deleting and recreating..."
    az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$MONGODB_ACI_NAME" --yes
fi

# Create MongoDB container with persistent storage
az container create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$MONGODB_ACI_NAME" \
    --image "mongo:7.0" \
    --vnet "$VNET_NAME" \
    --subnet "$SUBNET_NAME" \
    --ports 27017 \
    --cpu 1 \
    --memory 2 \
    --environment-variables \
        MONGO_INITDB_DATABASE=vibecoding_bot \
    --secure-environment-variables \
        MONGO_INITDB_ROOT_USERNAME=admin \
        MONGO_INITDB_ROOT_PASSWORD=vibecoding2024 \
    --azure-file-volume-account-name "$STORAGE_ACCOUNT_NAME" \
    --azure-file-volume-account-key "$STORAGE_KEY" \
    --azure-file-volume-share-name "mongodb-data" \
    --azure-file-volume-mount-path "/data/db" \
    --restart-policy Always

log_success "MongoDB container instance deployed successfully"

# Step 9: Get ACR credentials
log_info "Getting ACR credentials..."
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)

# Step 10: Deploy Bot Container Instance
log_info "Deploying bot container instance..."

# Check if bot container already exists
if az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$ACI_NAME" &> /dev/null; then
    log_info "Bot container already exists, deleting and recreating..."
    az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$ACI_NAME" --yes
fi

# Wait a moment for MongoDB to be ready
log_info "Waiting for MongoDB to be ready..."
sleep 30

# Create bot container
az container create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$ACI_NAME" \
    --image "$ACR_LOGIN_SERVER/vibecoding-bot:latest" \
    --registry-login-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --vnet "$VNET_NAME" \
    --subnet "$SUBNET_NAME" \
    --cpu 1 \
    --memory 1.5 \
    --environment-variables \
        PYTHONUNBUFFERED=1 \
    --secure-environment-variables \
        TELEGRAM_TOKEN="$TELEGRAM_TOKEN" \
        OPENAI_API_KEY="$OPENAI_API_KEY" \
        MONGODB_URI="$MONGODB_URI" \
    --restart-policy Always

log_success "Bot container instance deployed successfully"

# Step 11: Wait for containers to be ready
log_info "Waiting for containers to be ready..."
sleep 60

# Check container status
log_info "Checking container status..."
MONGODB_STATE=$(az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$MONGODB_ACI_NAME" --query instanceView.state -o tsv)
BOT_STATE=$(az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$ACI_NAME" --query instanceView.state -o tsv)

log_info "MongoDB container state: $MONGODB_STATE"
log_info "Bot container state: $BOT_STATE"

# Final status
log_success "🎉 Vibecoding Nights Bot deployed successfully to Azure!"
log_info "Resource Group: $AZURE_RESOURCE_GROUP"
log_info "Container Registry: $ACR_LOGIN_SERVER"
log_info "Bot Container: $ACI_NAME"
log_info "MongoDB Container: $MONGODB_ACI_NAME"
log_info "Key Vault: $KEY_VAULT_NAME"
log_info "Region: $AZURE_LOCATION"
log_info ""
log_info "To check the status:"
log_info "az container show --resource-group $AZURE_RESOURCE_GROUP --name $ACI_NAME"
log_info ""
log_info "To view logs:"
log_info "az container logs --resource-group $AZURE_RESOURCE_GROUP --name $ACI_NAME"
log_info ""
log_info "To stream logs:"
log_info "az container logs --resource-group $AZURE_RESOURCE_GROUP --name $ACI_NAME --follow"
