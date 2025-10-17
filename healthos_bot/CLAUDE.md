# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a **ChatGPT Telegram Bot** written in Python that provides a fast, unlimited interface to OpenAI's GPT models through Telegram. The bot supports multiple chat modes, voice messages, image generation with DALLE, and group chat functionality.

## Development Commands

### Local Development
```bash
# Setup configuration (required before first run)
mv config/config.example.yml config/config.yml
mv config/config.example.env config/config.env
# Edit config files with your tokens before running

# Run the bot with Docker (primary method)
docker-compose --env-file config/config.env up --build

# Run individual components for development
python3 bot/bot.py

# Package management with uv
uv add <package-name>
uv sync
```

### Azure Deployment
```bash
# Quick Azure deployment
./deploy-azure.sh

# See azure/README-AZURE-DEPLOYMENT.md for detailed instructions
```

## Architecture

### Core Components
- **bot/bot.py**: Main Telegram bot implementation with message handlers and OpenAI integration
- **bot/config.py**: Central configuration loader that combines YAML and ENV settings
- **bot/database.py**: MongoDB abstraction layer for user data, dialogs, and usage tracking
- **bot/openai_utils.py**: OpenAI API utilities for text generation, image creation, and token counting

### Configuration System
The bot uses a dual-configuration approach:
- **config/config.yml**: Main bot settings (tokens, allowed users, features)
- **config/config.env**: Environment-specific settings (database ports, paths)
- **config/chat_modes.yml**: Personality definitions and prompts for different bot modes
- **config/models.yml**: OpenAI model configurations and pricing

### Data Flow
1. Telegram messages received via python-telegram-bot handlers
2. User authentication checked against allowed_telegram_usernames
3. Messages processed through OpenAI API via openai_utils
4. Conversation history and usage tracked in MongoDB
5. Responses streamed back to Telegram with message streaming

### Deployment Architecture
- **Docker Compose**: Multi-container setup with bot, MongoDB, and Mongo Express
- **Azure Container Instances**: Cloud deployment with persistent storage
- **MongoDB**: User data, conversation history, and usage tracking
- **Azure Key Vault**: Secure token storage for production deployments

## Chat Modes System
Chat modes are defined in `config/chat_modes.yml` with each mode containing:
- `name`: Display name
- `model_type`: "text" or "image"
- `welcome_message`: Initial greeting
- `prompt_start`: System prompt defining the AI personality

The default "assistant" mode is a custom "Michalis Jr" persona that embodies a concise, casual coding community organizer style.

## Key Dependencies
- `python-telegram-bot`: Telegram Bot API wrapper
- `openai`: OpenAI API client
- `pymongo`: MongoDB driver
- `tiktoken`: Token counting for usage tracking
- `PyYAML`: Configuration file parsing