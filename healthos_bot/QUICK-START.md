# 🚀 Quick Start - Deploy in 5 Minutes

The **fastest** way to get your Telegram bot running on Azure.

## What You Need
- Azure CLI installed (`curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`)
- Azure account logged in (`az login`)
- Telegram Bot Token (from @BotFather)
- OpenAI API Key

## Deploy Now

```bash
./deploy-simple.sh
```

That's it! The script will:
1. Ask for your tokens
2. Create Azure resources
3. Deploy your bot
4. Give you management commands

## What You Get
- ✅ **Working bot** in 5 minutes
- ✅ **~$25/month** cost
- ✅ **Auto-restart** on failures
- ✅ **Azure monitoring** included

## What You Don't Get
- ❌ **No persistent storage** (bot forgets conversations on restart)
- ❌ **No database** (can't store user data)
- ❌ **No custom networking**

## Management Commands

After deployment, use these commands (replace `my-bot-rg` and `my-telegram-bot` with your values):

```bash
# Check if running
az container show --resource-group my-bot-rg --name my-telegram-bot --query instanceView.state

# View logs
az container logs --resource-group my-bot-rg --name my-telegram-bot

# Stream logs live
az container logs --resource-group my-bot-rg --name my-telegram-bot --follow

# Restart bot
az container restart --resource-group my-bot-rg --name my-telegram-bot

# Delete everything
az group delete --name my-bot-rg --yes --no-wait
```

## Upgrade Later

When you need persistence and advanced features:
```bash
./deploy-azure.sh
```

This gives you the full production setup with database, networking, and persistent storage.

---

**Ready?** Run `./deploy-simple.sh` and have your bot live in 5 minutes! 🎉
