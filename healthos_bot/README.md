# ChatGPT Telegram Bot: **GPT-4. Fast. No daily limits. Special chat modes**


We all love [chat.openai.com](https://chat.openai.com), but... It's TERRIBLY laggy, has daily limits, and is only accessible through an archaic web interface.

This repo is ChatGPT re-created as Telegram Bot. **And it works great.**

You can deploy your own bot, or use mine: [@jadvebot](https://t.me/jadvebot) (Our web: https://jadve.com)

## Features
- Low latency replies (it usually takes about 3-5 seconds)
- No request limits
- Message streaming (watch demo)
- GPT-4 and GPT-4 Turbo support
- GPT-4 Vision support
- Group Chat support (/help_group_chat to get instructions)
- DALLE 2 (choose 👩‍🎨 Artist mode to generate images)
- Voice message recognition
- Code highlighting
- 15 special chat modes: 👩🏼‍🎓 Assistant, 👩🏼‍💻 Code Assistant, 👩‍🎨 Artist, 🧠 Psychologist, 🚀 Elon Musk and other. You can easily create your own chat modes by editing `config/chat_modes.yml`
- Support of [ChatGPT API](https://platform.openai.com/docs/guides/chat/introduction)
- List of allowed Telegram users
- Track $ balance spent on OpenAI API

## Bot commands
- `/retry` – Regenerate last bot answer
- `/new` – Start new dialog
- `/mode` – Select chat mode
- `/balance` – Show balance
- `/settings` – Show settings
- `/help` – Show help

## Setup
1. Get your [OpenAI API](https://openai.com/api/) key

2. Get your Telegram bot token from [@BotFather](https://t.me/BotFather)

3. Edit `config/config.example.yml` to set your tokens and run 2 commands below (*if you're advanced user, you can also edit* `config/config.example.env`):
    ```bash
    mv config/config.example.yml config/config.yml
    mv config/config.example.env config/config.env
    ```

4. 🔥 And now **run**:
    ```bash
    docker-compose --env-file config/config.env up --build
    ```

## Cloud Deployment

### 🚀 Super Simple (5 minutes)
The absolute easiest way - no persistent storage, just get it running:

```bash
# One-command deployment
./deploy-simple.sh
```

See [Simple Azure Deploy Guide](SIMPLE-AZURE-DEPLOY.md) for manual steps.

### 🏗️ Full Production Setup
Complete deployment with persistent storage and networking:

```bash
# Full deployment to Azure
./deploy-azure.sh
```

For detailed Azure deployment instructions, see [Azure Deployment Guide](azure/README-AZURE-DEPLOYMENT.md).

### Cloud Features
- **Container Registry**: Push your bot image to Azure Container Registry (ACR)
- **Managed Containers**: Run on Azure Container Instances (ACI)
- **Secrets Management**: Store tokens securely in Azure Key Vault
- **Persistent Storage**: MongoDB with Azure Files persistent volumes
- **Networking**: Private virtual networks for security
- **Monitoring**: Built-in logging and monitoring with Azure Monitor
- **Auto-scaling**: Automatic restarts and scaling capabilities
