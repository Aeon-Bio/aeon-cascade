#!/bin/bash

# Vibecoding Nights Bot - Azure Cleanup Script
# This script removes all Azure resources created by the deployment script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Load configuration
if [ -f "../config/config.env" ]; then
    source ../config/config.env
    log_info "Loaded configuration from config/config.env"
else
    log_error "config/config.env not found. Please run from project root or azure directory."
    exit 1
fi

# Set default values if not provided
AZURE_RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-"vibecoding-rg"}
AZURE_LOCATION=${AZURE_LOCATION:-"eastus"}
ACR_NAME=${ACR_NAME:-"frontiertower"}
ACI_NAME=${ACI_NAME:-"vibecoding-bot"}
MONGODB_ACI_NAME=${MONGODB_ACI_NAME:-"vibecoding-mongodb"}

log_warning "⚠️  This will DELETE all Azure resources for the Vibecoding Bot!"
log_warning "This action cannot be undone."
echo
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    log_info "Cleanup cancelled."
    exit 0
fi

log_info "Starting cleanup of Azure resources..."

# Check Azure CLI authentication
if ! az account show &> /dev/null; then
    log_error "Azure CLI not authenticated. Please run 'az login' first."
    exit 1
fi

# Set subscription if provided
if [ -n "$AZURE_SUBSCRIPTION_ID" ]; then
    az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    log_info "Using Azure subscription: $AZURE_SUBSCRIPTION_ID"
fi

# Delete Container Instances
log_info "Deleting container instances..."

if az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$ACI_NAME" &> /dev/null; then
    log_info "Deleting bot container instance: $ACI_NAME"
    az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$ACI_NAME" --yes
    log_success "Bot container instance deleted"
else
    log_info "Bot container instance not found"
fi

if az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$MONGODB_ACI_NAME" &> /dev/null; then
    log_info "Deleting MongoDB container instance: $MONGODB_ACI_NAME"
    az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$MONGODB_ACI_NAME" --yes
    log_success "MongoDB container instance deleted"
else
    log_info "MongoDB container instance not found"
fi

# Delete Container Registry (optional - comment out if you want to keep it)
log_info "Deleting Azure Container Registry..."
if az acr show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    log_warning "This will delete the container registry and all images!"
    read -p "Delete Container Registry '$ACR_NAME'? (y/N): " delete_acr
    if [ "$delete_acr" = "y" ] || [ "$delete_acr" = "Y" ]; then
        az acr delete --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --yes
        log_success "Container Registry deleted: $ACR_NAME"
    else
        log_info "Container Registry preserved: $ACR_NAME"
    fi
else
    log_info "Container Registry not found: $ACR_NAME"
fi

# Delete Key Vaults
log_info "Deleting Key Vaults..."
KEY_VAULTS=$(az keyvault list --resource-group "$AZURE_RESOURCE_GROUP" --query '[].name' -o tsv 2>/dev/null || echo "")

if [ -n "$KEY_VAULTS" ]; then
    for kv in $KEY_VAULTS; do
        if [[ "$kv" == *"vibecoding"* ]]; then
            log_info "Deleting Key Vault: $kv"
            az keyvault delete --name "$kv" --resource-group "$AZURE_RESOURCE_GROUP"
            # Purge the Key Vault to completely remove it
            az keyvault purge --name "$kv" --location "$AZURE_LOCATION" 2>/dev/null || true
            log_success "Key Vault deleted: $kv"
        fi
    done
else
    log_info "No Key Vaults found"
fi

# Delete Storage Accounts
log_info "Deleting Storage Accounts..."
STORAGE_ACCOUNTS=$(az storage account list --resource-group "$AZURE_RESOURCE_GROUP" --query '[].name' -o tsv 2>/dev/null || echo "")

if [ -n "$STORAGE_ACCOUNTS" ]; then
    for sa in $STORAGE_ACCOUNTS; do
        if [[ "$sa" == *"vibecoding"* ]]; then
            log_info "Deleting Storage Account: $sa"
            az storage account delete --name "$sa" --resource-group "$AZURE_RESOURCE_GROUP" --yes
            log_success "Storage Account deleted: $sa"
        fi
    done
else
    log_info "No Storage Accounts found"
fi

# Delete Virtual Networks
log_info "Deleting Virtual Networks..."
VNETS=$(az network vnet list --resource-group "$AZURE_RESOURCE_GROUP" --query '[].name' -o tsv 2>/dev/null || echo "")

if [ -n "$VNETS" ]; then
    for vnet in $VNETS; do
        if [[ "$vnet" == *"vibecoding"* ]]; then
            log_info "Deleting Virtual Network: $vnet"
            az network vnet delete --name "$vnet" --resource-group "$AZURE_RESOURCE_GROUP"
            log_success "Virtual Network deleted: $vnet"
        fi
    done
else
    log_info "No Virtual Networks found"
fi

# Delete Network Security Groups
log_info "Deleting Network Security Groups..."
NSGS=$(az network nsg list --resource-group "$AZURE_RESOURCE_GROUP" --query '[].name' -o tsv 2>/dev/null || echo "")

if [ -n "$NSGS" ]; then
    for nsg in $NSGS; do
        if [[ "$nsg" == *"vibecoding"* ]]; then
            log_info "Deleting Network Security Group: $nsg"
            az network nsg delete --name "$nsg" --resource-group "$AZURE_RESOURCE_GROUP"
            log_success "Network Security Group deleted: $nsg"
        fi
    done
else
    log_info "No Network Security Groups found"
fi

# Option to delete the entire resource group
log_warning "Do you want to delete the entire resource group?"
log_warning "This will remove ALL resources in the resource group: $AZURE_RESOURCE_GROUP"
read -p "Delete entire resource group? (y/N): " delete_rg

if [ "$delete_rg" = "y" ] || [ "$delete_rg" = "Y" ]; then
    log_info "Deleting resource group: $AZURE_RESOURCE_GROUP"
    az group delete --name "$AZURE_RESOURCE_GROUP" --yes --no-wait
    log_success "Resource group deletion initiated: $AZURE_RESOURCE_GROUP"
    log_info "Note: Resource group deletion is running in the background and may take several minutes to complete."
else
    log_info "Resource group preserved: $AZURE_RESOURCE_GROUP"
fi

# Clean up any remaining container groups
log_info "Checking for any remaining container groups..."
CONTAINER_GROUPS=$(az container list --resource-group "$AZURE_RESOURCE_GROUP" --query '[].name' -o tsv 2>/dev/null || echo "")

if [ -n "$CONTAINER_GROUPS" ]; then
    for cg in $CONTAINER_GROUPS; do
        if [[ "$cg" == *"vibecoding"* ]]; then
            log_info "Deleting remaining container group: $cg"
            az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$cg" --yes
            log_success "Container group deleted: $cg"
        fi
    done
else
    log_info "No remaining container groups found"
fi

log_success "🧹 Azure cleanup completed successfully!"
log_info "All Vibecoding Bot resources have been removed from Azure."

# Show remaining resources in the resource group (if it still exists)
if az group show --name "$AZURE_RESOURCE_GROUP" &> /dev/null; then
    log_info ""
    log_info "Remaining resources in resource group '$AZURE_RESOURCE_GROUP':"
    az resource list --resource-group "$AZURE_RESOURCE_GROUP" --query '[].{Name:name, Type:type, Location:location}' -o table 2>/dev/null || log_info "No resources found or resource group deleted."
fi
