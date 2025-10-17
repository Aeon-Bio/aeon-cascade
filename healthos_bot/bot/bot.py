import io
import logging
import asyncio
import traceback
import html
import json
from datetime import datetime

import telegram
from telegram import (
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    AIORateLimiter,
    filters
)
from telegram.constants import ParseMode, ChatAction

import config
import database

import base64
from ddgs import DDGS

# setup logger BEFORE using it
logger = logging.getLogger(__name__)

# setup
db = database.Database()

# Import indra_agent for health intelligence (direct Python import, no HTTP)
try:
    from indra_agent.core.client import INDRAAgentClient
    from indra_agent.core.models import (
        CausalDiscoveryRequest,
        UserContext,
        Query,
        LocationHistory,
        RequestOptions
    )
    INDRA_AVAILABLE = True
    logger.info("INDRA agent modules imported successfully")
except ImportError as e:
    INDRA_AVAILABLE = False
    logger.warning(f"INDRA agent not available: {e}")

user_semaphores = {}
user_tasks = {}

# Initialize INDRA client (singleton, reused across requests)
indra_client = None
if INDRA_AVAILABLE:
    try:
        indra_client = INDRAAgentClient()
        logger.info("INDRA agent client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize INDRA client: {e}")
        INDRA_AVAILABLE = False

HELP_MESSAGE = """Commands:
⚪ /retry – Regenerate last bot answer
⚪ /new – Start new dialog
⚪ /mode – Select chat mode
⚪ /settings – Show settings
⚪ /balance – Show balance
⚪ /help – Show help

🎨 Generate images from text prompts in <b>👩‍🎨 Artist</b> /mode
👥 Add bot to <b>group chat</b>: /help_group_chat
🎤 You can send <b>Voice Messages</b> instead of text
"""

HELP_GROUP_CHAT_MESSAGE = """You can add bot to any <b>group chat</b> to help and entertain its participants!

Instructions (see <b>video</b> below):
1. Add the bot to the group chat
2. Make it an <b>admin</b>, so that it can see messages (all other rights can be restricted)
3. You're awesome!

To get a reply from the bot in the chat – @ <b>tag</b> it or <b>reply</b> to its message.
For example: "{bot_username} write a poem about Telegram"
"""


def split_text_into_chunks(text, chunk_size):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


async def search_web(query: str, max_results: int = 5):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
    except Exception as e:
        logger.error(f"Search error: {e}")
    return results


def is_health_query(message_text: str) -> bool:
    """Detect if message is a health-related query for INDRA.

    Health keywords indicate biomarker tracking, environmental impact,
    genetic analysis, or causal pathway discovery.
    """
    if not message_text:
        return False

    message_lower = message_text.lower()

    # Health/biomarker keywords
    health_keywords = [
        'biomarker', 'crp', 'il-6', 'inflammation', 'oxidative stress',
        'pollution', 'pm2.5', 'air quality', 'exposure',
        'gene', 'genetic', 'variant', 'gstm1',
        'health', 'risk', 'causal', 'pathway', 'mechanism',
        'environmental', 'affect', 'impact', 'influence',
        'molecular', 'protein', 'cytokine'
    ]

    # Check if message contains health keywords
    return any(keyword in message_lower for keyword in health_keywords)


async def query_indra_health_system(user_id: int, message_text: str) -> dict:
    """Query INDRA agent system for health intelligence.

    Args:
        user_id: Telegram user ID
        message_text: User's health query

    Returns:
        dict with 'success', 'response' (formatted text), and 'graph' (raw data)
    """
    if not INDRA_AVAILABLE or indra_client is None:
        return {
            'success': False,
            'response': "Health intelligence system is not available. Using general AI instead.",
            'graph': None
        }

    try:
        import uuid

        # Build user context from database
        user_context_dict = {
            'user_id': str(user_id),
            'genetics': db.get_user_attribute(user_id, 'health_genetics') or {},
            'current_biomarkers': db.get_user_attribute(user_id, 'health_biomarkers') or {},
            'location_history': db.get_user_attribute(user_id, 'health_location_history') or []
        }

        user_context = UserContext(**user_context_dict)

        # Create request
        request = CausalDiscoveryRequest(
            request_id=str(uuid.uuid4()),
            user_context=user_context,
            query=Query(text=message_text),
            options=RequestOptions()
        )

        # Call INDRA agent directly (no HTTP)
        logger.info(f"Calling INDRA agent for user {user_id}: {message_text}")
        response = await indra_client.process_request(request)

        # Format response for Telegram
        if hasattr(response, 'causal_graph'):
            formatted_response = format_indra_response(response)
            return {
                'success': True,
                'response': formatted_response,
                'graph': response
            }
        else:
            # Error response
            error_msg = response.error.message if hasattr(response, 'error') else "Unknown error"
            return {
                'success': False,
                'response': f"Could not process health query: {error_msg}",
                'graph': None
            }

    except Exception as e:
        logger.error(f"Error querying INDRA system: {e}", exc_info=True)
        return {
            'success': False,
            'response': f"Health system error: {str(e)}. Using general AI instead.",
            'graph': None
        }


def format_indra_response(response) -> str:
    """Format INDRA causal discovery response for Telegram display.

    Args:
        response: CausalDiscoveryResponse object

    Returns:
        Formatted markdown/HTML text for Telegram
    """
    graph = response.causal_graph
    metadata = response.metadata
    explanations = response.explanations

    # Build formatted message
    lines = ["🧬 <b>Health Intelligence Report</b>\n"]

    # Explanations (key insights)
    lines.append("📊 <b>Key Insights:</b>")
    for i, explanation in enumerate(explanations, 1):
        lines.append(f"{i}. {explanation}")
    lines.append("")

    # Causal graph summary
    lines.append(f"🔬 <b>Causal Analysis:</b>")
    lines.append(f"• {len(graph.nodes)} biological entities identified")
    lines.append(f"• {len(graph.edges)} causal relationships found")
    lines.append(f"• Based on {metadata.total_evidence_papers} scientific papers")
    lines.append(f"• Analysis time: {metadata.query_time_ms}ms")
    lines.append("")

    # Show top causal paths (most significant edges)
    if graph.edges:
        lines.append("🔗 <b>Top Causal Pathways:</b>")
        # Sort by evidence count
        sorted_edges = sorted(graph.edges,
                             key=lambda e: e.evidence.count,
                             reverse=True)[:5]

        for edge in sorted_edges:
            # Find node labels
            source_label = next((n.label for n in graph.nodes if n.id == edge.source), edge.source)
            target_label = next((n.label for n in graph.nodes if n.id == edge.target), edge.target)

            relationship_symbol = {
                'activates': '➡️',
                'inhibits': '⊣',
                'increases': '⬆️',
                'decreases': '⬇️'
            }.get(edge.relationship, '→')

            lines.append(
                f"  {source_label} {relationship_symbol} {target_label}\n"
                f"  <i>Evidence: {edge.evidence.count} papers, "
                f"Effect: {edge.effect_size:.2f}, "
                f"Lag: {edge.temporal_lag_hours}h</i>"
            )
        lines.append("")

    # Genetic modifiers
    if graph.genetic_modifiers:
        lines.append("🧬 <b>Genetic Factors:</b>")
        for modifier in graph.genetic_modifiers:
            effect_emoji = "⬆️" if modifier.effect_type == "amplifies" else "⬇️"
            lines.append(f"  {effect_emoji} {modifier.variant}: {modifier.effect_type} effect by {modifier.magnitude:.1f}x")
        lines.append("")

    lines.append("💡 <i>This analysis uses INDRA bio-ontology for evidence-based causal pathways.</i>")

    return "\n".join(lines)


async def optimize_search_query(user_query: str) -> str:
    """Simple pass-through without OpenAI optimization"""
    return user_query


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
    if not db.check_if_user_exists(user.id):
        db.add_new_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name= user.last_name
        )
        db.start_new_dialog(user.id)

    if db.get_user_attribute(user.id, "current_dialog_id") is None:
        db.start_new_dialog(user.id)

    if user.id not in user_semaphores:
        user_semaphores[user.id] = asyncio.Semaphore(1)

    if db.get_user_attribute(user.id, "current_model") is None:
        db.set_user_attribute(user.id, "current_model", config.models["available_text_models"][0])

    # back compatibility for n_used_tokens field
    n_used_tokens = db.get_user_attribute(user.id, "n_used_tokens")
    if isinstance(n_used_tokens, int) or isinstance(n_used_tokens, float):  # old format
        new_n_used_tokens = {
            config.models["available_text_models"][0]: {
                "n_input_tokens": 0,
                "n_output_tokens": n_used_tokens
            }
        }
        db.set_user_attribute(user.id, "n_used_tokens", new_n_used_tokens)

    # voice message transcription
    if db.get_user_attribute(user.id, "n_transcribed_seconds") is None:
        db.set_user_attribute(user.id, "n_transcribed_seconds", 0.0)

    # image generation
    if db.get_user_attribute(user.id, "n_generated_images") is None:
        db.set_user_attribute(user.id, "n_generated_images", 0)


async def is_bot_mentioned(update: Update, context: CallbackContext):
    """
    Enhanced function to check if the bot is mentioned in a group chat.
    Returns True for private chats, or if bot is mentioned/replied to in groups.
    """
    try:
        message = update.message
        if not message:
            return False

        # Always respond in private chats
        if message.chat.type == "private":
            return True

        bot_username = context.bot.username
        if not bot_username:
            logger.warning("Bot username not available for mention detection")
            return True  # Default to responding if we can't check

        # Check for @botname mentions in message text
        message_text = message.text or ""
        if message_text and f"@{bot_username}" in message_text:
            return True

        # Check for @botname mentions in caption (for photos/videos/documents)
        caption_text = message.caption or ""
        if caption_text and f"@{bot_username}" in caption_text:
            return True

        # Check if replying to bot's message
        if message.reply_to_message and message.reply_to_message.from_user:
            if message.reply_to_message.from_user.id == context.bot.id:
                return True

        # Check message entities for mentions (more robust detection)
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    # Extract the mentioned username from the text
                    start = entity.offset
                    end = entity.offset + entity.length
                    mentioned_user = message_text[start:end]
                    if mentioned_user == f"@{bot_username}":
                        return True

        # Check caption entities for mentions
        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type == "mention":
                    # Extract the mentioned username from the caption
                    start = entity.offset
                    end = entity.offset + entity.length
                    mentioned_user = caption_text[start:end]
                    if mentioned_user == f"@{bot_username}":
                        return True

        return False

    except AttributeError as e:
        logger.error(f"AttributeError in is_bot_mentioned: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in is_bot_mentioned: {e}")
        return False


def clean_message_text(message_text: str, bot_username: str) -> str:
    """
    Remove bot mentions from message text in a more robust way.
    Handles various mention formats and positions.
    """
    if not message_text or not bot_username:
        return message_text or ""

    import re

    # Create pattern to match @botname mentions
    # This pattern handles:
    # - @botname at the beginning
    # - @botname in the middle
    # - @botname at the end
    # - Multiple @botname mentions
    mention_pattern = rf"@{re.escape(bot_username)}"

    # Remove all mentions of the bot
    cleaned_text = re.sub(mention_pattern, "", message_text, flags=re.IGNORECASE)

    # Clean up extra whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text


def get_chat_info(update: Update) -> dict:
    """
    Extract relevant chat information for logging and debugging.
    """
    if not update or not update.message:
        return {}

    chat = update.message.chat
    user = update.message.from_user

    return {
        "chat_id": chat.id,
        "chat_type": chat.type,
        "chat_title": getattr(chat, 'title', None),
        "user_id": user.id if user else None,
        "username": user.username if user else None,
        "is_bot": user.is_bot if user else None,
    }


async def log_group_interaction(update: Update, context: CallbackContext, interaction_type: str):
    """
    Log group chat interactions for debugging and monitoring.
    """
    try:
        chat_info = get_chat_info(update)
        if chat_info.get("chat_type") != "private":
            logger.info(f"Group interaction - {interaction_type}: "
                       f"Chat: {chat_info.get('chat_title', 'Unknown')} ({chat_info.get('chat_id')}), "
                       f"User: {chat_info.get('username', 'Unknown')} ({chat_info.get('user_id')})")
    except Exception as e:
        logger.error(f"Error logging group interaction: {e}")


async def validate_group_chat_setup(context: CallbackContext) -> bool:
    """
    Validate that the bot is properly configured for group chat interactions.
    """
    try:
        if not context.bot:
            logger.error("Bot context is not available")
            return False

        if not context.bot.username:
            logger.error("Bot username is not available - this is required for group chat mentions")
            return False

        return True
    except Exception as e:
        logger.error(f"Error validating group chat setup: {e}")
        return False


async def start_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    db.start_new_dialog(user_id)

    reply_text = "Hi! I'm Michalis Jr🤖\n\n"
    reply_text += HELP_MESSAGE

    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
    await show_chat_modes_handle(update, context)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def help_group_chat_handle(update: Update, context: CallbackContext):
     await register_user_if_not_exists(update, context, update.message.from_user)
     user_id = update.message.from_user.id
     db.set_user_attribute(user_id, "last_interaction", datetime.now())

     text = HELP_GROUP_CHAT_MESSAGE.format(bot_username="@" + context.bot.username)

     await update.message.reply_text(text, parse_mode=ParseMode.HTML)
     await update.message.reply_video(config.help_group_chat_video_path)


async def search_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    if not context.args:
        await update.message.reply_text("❓ Usage: /search <query>")
        return

    query = " ".join(context.args)

    # In group chats, check if the bot is mentioned or the command is direct
    if update.message.chat.type != "private":
        if not await is_bot_mentioned(update, context):
            return

    await update.message.chat.send_action(action="typing")

    # Optimize the search query using LLM
    optimized_query = await optimize_search_query(query)

    results = await search_web(optimized_query, max_results=5)

    if not results:
        await update.message.reply_text("🥲 No results found.")
        return

    if optimized_query != query:
        reply_text = f"🔎 Results for \"{query}\":\n<i>🔧 Optimized query: {optimized_query}</i>\n\n"
    else:
        reply_text = f"🔎 Results for \"{query}\":\n\n"
    for i, r in enumerate(results, start=1):
        title = r.get("title", "No title")
        link = r.get("href", "")
        snippet = r.get("body", "")
        reply_text += f"{i}. <b>{title}</b>\n{snippet}\n🔗 {link}\n\n"

    await update.message.reply_text(
        reply_text[:4000],
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

    # Store search query and results in dialog history
    search_user_message = f"/search {query}"
    new_dialog_message = {"user": [{"type": "text", "text": search_user_message}], "bot": reply_text[:4000], "date": datetime.now()}
    db.set_dialog_messages(
        user_id,
        db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
        dialog_id=None
    )


async def retry_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
    if len(dialog_messages) == 0:
        await update.message.reply_text("No message to retry 🤷‍♂️")
        return

    last_dialog_message = dialog_messages.pop()
    db.set_dialog_messages(user_id, dialog_messages, dialog_id=None)  # last message was removed from the context

    await message_handle(update, context, message=last_dialog_message["user"], use_new_dialog_timeout=False)

async def _vision_message_handle_fn(
    update: Update, context: CallbackContext, use_new_dialog_timeout: bool = True
):
    """Vision/image processing disabled (was using OpenAI GPT-4 Vision)"""
    await update.message.reply_text(
        "📸 Image analysis is currently disabled. This bot now uses AWS Bedrock for text responses only.",
        parse_mode=ParseMode.HTML
    )

async def unsupport_message_handle(update: Update, context: CallbackContext, message=None):
    error_text = f"I don't know how to read files or videos. Send the picture in normal mode (Quick Mode)."
    logger.error(error_text)
    await update.message.reply_text(error_text)
    return

async def message_handle(update: Update, context: CallbackContext, message=None, use_new_dialog_timeout=True):
    # validate group chat setup for non-private chats
    if update.message and update.message.chat.type != "private":
        if not await validate_group_chat_setup(context):
            logger.error("Group chat setup validation failed")
            return

    # check if bot was mentioned (for group chats)
    if not await is_bot_mentioned(update, context):
        return

    # log group interactions for debugging
    await log_group_interaction(update, context, "message_received")

    # check if message is edited
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    _message = message or update.message.text

    # remove bot mention (in group chats) using enhanced cleaning
    if update.message.chat.type != "private":
        _message = clean_message_text(_message, context.bot.username)

    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")

    if chat_mode == "artist":
        await generate_image_handle(update, context, message=message)
        return

    current_model = db.get_user_attribute(user_id, "current_model")

    async def message_handle_fn():
        # new dialog timeout
        if use_new_dialog_timeout:
            if (datetime.now() - db.get_user_attribute(user_id, "last_interaction")).seconds > config.new_dialog_timeout and len(db.get_dialog_messages(user_id)) > 0:
                db.start_new_dialog(user_id)
                await update.message.reply_text(f"Starting new dialog due to timeout (<b>{config.chat_modes[chat_mode]['name']}</b> mode) ✅", parse_mode=ParseMode.HTML)
        db.set_user_attribute(user_id, "last_interaction", datetime.now())

        # in case of CancelledError
        n_input_tokens, n_output_tokens = 0, 0

        try:
            # Check if message is empty
            if _message is None or len(_message.strip()) == 0:
                if update.message.chat.type == "private":
                    await update.message.reply_text("🥲 You sent <b>empty message</b>. Please, try again!", parse_mode=ParseMode.HTML)
                else:
                    # In group chats, provide more helpful guidance
                    await update.message.reply_text(
                        f"👋 Hi! You mentioned me but didn't include a message. Try: <code>@{context.bot.username} your question here</code>",
                        parse_mode=ParseMode.HTML
                    )
                return

            # Use INDRA/Bedrock for ALL queries (not just health)
            if not INDRA_AVAILABLE:
                await update.message.reply_text(
                    "❌ The bot is currently unavailable. AWS Bedrock integration is not initialized.",
                    parse_mode=ParseMode.HTML
                )
                return

            logger.info(f"Processing query from user {user_id}: {_message[:50]}...")

            # send placeholder
            placeholder_message = await update.message.reply_text("🤖 Thinking...")

            # send typing action
            await update.message.chat.send_action(action="typing")

            # Query INDRA system (works for both health and general queries)
            indra_result = await query_indra_health_system(user_id, _message)

            if indra_result['success']:
                # Use INDRA/Bedrock response
                answer = indra_result['response']

                # Update placeholder with result
                try:
                    await context.bot.edit_message_text(
                        answer,
                        chat_id=placeholder_message.chat_id,
                        message_id=placeholder_message.message_id,
                        parse_mode=ParseMode.HTML
                    )
                except telegram.error.BadRequest:
                    # If message is too long or has formatting issues
                    await context.bot.edit_message_text(
                        answer[:4096],
                        chat_id=placeholder_message.chat_id,
                        message_id=placeholder_message.message_id,
                        parse_mode=ParseMode.HTML
                    )

                # Store in dialog history
                new_dialog_message = {
                    "user": [{"type": "text", "text": _message}],
                    "bot": answer,
                    "date": datetime.now(),
                    "source": "aws_bedrock"
                }
                db.set_dialog_messages(
                    user_id,
                    db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
                    dialog_id=None
                )

                # No token tracking for AWS Bedrock (tracked separately)
                return
            else:
                # INDRA failed
                error_msg = f"❌ Failed to process your message. Reason: {indra_result['response']}"
                await placeholder_message.edit_text(error_msg, parse_mode=ParseMode.HTML)
                return

        except asyncio.CancelledError:
            logger.info(f"Message handling cancelled for user {user_id}")
            raise

        except Exception as e:
            error_text = f"Something went wrong during completion. Reason: {e}"
            logger.error(error_text)
            await update.message.reply_text(error_text)
            return

    async with user_semaphores[user_id]:
        # Vision/photo support removed (was using OpenAI GPT-4 Vision)
        if update.message.photo is not None and len(update.message.photo) > 0:
            await update.message.reply_text(
                "📸 Image analysis is currently disabled. Please describe the image in text.",
                parse_mode=ParseMode.HTML
            )
            return

        task = asyncio.create_task(
            message_handle_fn()
        )            

        user_tasks[user_id] = task

        try:
            await task
        except asyncio.CancelledError:
            await update.message.reply_text("✅ Canceled", parse_mode=ParseMode.HTML)
        else:
            pass
        finally:
            if user_id in user_tasks:
                del user_tasks[user_id]


async def is_previous_message_not_answered_yet(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    if user_semaphores[user_id].locked():
        text = "⏳ Please <b>wait</b> for a reply to the previous message\n"
        text += "Or you can /cancel it"
        await update.message.reply_text(text, reply_to_message_id=update.message.id, parse_mode=ParseMode.HTML)
        return True
    else:
        return False


async def voice_message_handle(update: Update, context: CallbackContext):
    # validate group chat setup for non-private chats
    if update.message and update.message.chat.type != "private":
        if not await validate_group_chat_setup(context):
            logger.error("Group chat setup validation failed for voice message")
            return

    # check if bot was mentioned (for group chats)
    if not await is_bot_mentioned(update, context):
        return

    # log group interactions for debugging
    await log_group_interaction(update, context, "voice_message_received")

    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # Voice transcription disabled (OpenAI Whisper removed)
    await update.message.reply_text(
        "🎤 Voice message transcription is currently disabled. Please send text messages instead.",
        parse_mode=ParseMode.HTML
    )


async def generate_image_handle(update: Update, context: CallbackContext, message=None):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # Image generation disabled (OpenAI removed)
    await update.message.reply_text(
        "🎨 Image generation is currently disabled. This bot now uses AWS Bedrock for text responses only.",
        parse_mode=ParseMode.HTML
    )


async def new_dialog_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    db.set_user_attribute(user_id, "current_model", config.models["available_text_models"][0])

    db.start_new_dialog(user_id)
    await update.message.reply_text("Starting new dialog ✅")

    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    await update.message.reply_text(f"{config.chat_modes[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def cancel_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    if user_id in user_tasks:
        task = user_tasks[user_id]
        task.cancel()
    else:
        await update.message.reply_text("<i>Nothing to cancel...</i>", parse_mode=ParseMode.HTML)


def get_chat_mode_menu(page_index: int):
    n_chat_modes_per_page = config.n_chat_modes_per_page
    text = f"Select <b>chat mode</b> ({len(config.chat_modes)} modes available):"

    # buttons
    chat_mode_keys = list(config.chat_modes.keys())
    page_chat_mode_keys = chat_mode_keys[page_index * n_chat_modes_per_page:(page_index + 1) * n_chat_modes_per_page]

    keyboard = []
    for chat_mode_key in page_chat_mode_keys:
        name = config.chat_modes[chat_mode_key]["name"]
        keyboard.append([InlineKeyboardButton(name, callback_data=f"set_chat_mode|{chat_mode_key}")])

    # pagination
    if len(chat_mode_keys) > n_chat_modes_per_page:
        is_first_page = (page_index == 0)
        is_last_page = ((page_index + 1) * n_chat_modes_per_page >= len(chat_mode_keys))

        if is_first_page:
            keyboard.append([
                InlineKeyboardButton("»", callback_data=f"show_chat_modes|{page_index + 1}")
            ])
        elif is_last_page:
            keyboard.append([
                InlineKeyboardButton("«", callback_data=f"show_chat_modes|{page_index - 1}"),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("«", callback_data=f"show_chat_modes|{page_index - 1}"),
                InlineKeyboardButton("»", callback_data=f"show_chat_modes|{page_index + 1}")
            ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    return text, reply_markup


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    text, reply_markup = get_chat_mode_menu(0)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def show_chat_modes_callback_handle(update: Update, context: CallbackContext):
     await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
     if await is_previous_message_not_answered_yet(update.callback_query, context): return

     user_id = update.callback_query.from_user.id
     db.set_user_attribute(user_id, "last_interaction", datetime.now())

     query = update.callback_query
     await query.answer()

     page_index = int(query.data.split("|")[1])
     if page_index < 0:
         return

     text, reply_markup = get_chat_mode_menu(page_index)
     try:
         await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
     except telegram.error.BadRequest as e:
         if str(e).startswith("Message is not modified"):
             pass


async def set_chat_mode_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    chat_mode = query.data.split("|")[1]

    db.set_user_attribute(user_id, "current_chat_mode", chat_mode)
    db.start_new_dialog(user_id)

    await context.bot.send_message(
        update.callback_query.message.chat.id,
        f"{config.chat_modes[chat_mode]['welcome_message']}",
        parse_mode=ParseMode.HTML
    )


def get_settings_menu(user_id: int):
    current_model = db.get_user_attribute(user_id, "current_model")
    text = config.models["info"][current_model]["description"]

    text += "\n\n"
    score_dict = config.models["info"][current_model]["scores"]
    for score_key, score_value in score_dict.items():
        text += "🟢" * score_value + "⚪️" * (5 - score_value) + f" – {score_key}\n\n"

    text += "\nSelect <b>model</b>:"

    # buttons to choose models
    buttons = []
    for model_key in config.models["available_text_models"]:
        title = config.models["info"][model_key]["name"]
        if model_key == current_model:
            title = "✅ " + title

        buttons.append(
            InlineKeyboardButton(title, callback_data=f"set_settings|{model_key}")
        )
    reply_markup = InlineKeyboardMarkup([buttons])

    return text, reply_markup


async def settings_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    text, reply_markup = get_settings_menu(user_id)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def set_settings_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    _, model_key = query.data.split("|")
    db.set_user_attribute(user_id, "current_model", model_key)
    db.start_new_dialog(user_id)

    text, reply_markup = get_settings_menu(user_id)
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest as e:
        if str(e).startswith("Message is not modified"):
            pass


async def show_balance_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # count total usage statistics
    total_n_spent_dollars = 0
    total_n_used_tokens = 0

    n_used_tokens_dict = db.get_user_attribute(user_id, "n_used_tokens")
    n_generated_images = db.get_user_attribute(user_id, "n_generated_images")
    n_transcribed_seconds = db.get_user_attribute(user_id, "n_transcribed_seconds")

    details_text = "🏷️ Details:\n"
    for model_key in sorted(n_used_tokens_dict.keys()):
        n_input_tokens, n_output_tokens = n_used_tokens_dict[model_key]["n_input_tokens"], n_used_tokens_dict[model_key]["n_output_tokens"]
        total_n_used_tokens += n_input_tokens + n_output_tokens

        n_input_spent_dollars = config.models["info"][model_key]["price_per_1000_input_tokens"] * (n_input_tokens / 1000)
        n_output_spent_dollars = config.models["info"][model_key]["price_per_1000_output_tokens"] * (n_output_tokens / 1000)
        total_n_spent_dollars += n_input_spent_dollars + n_output_spent_dollars

        details_text += f"- {model_key}: <b>{n_input_spent_dollars + n_output_spent_dollars:.03f}$</b> / <b>{n_input_tokens + n_output_tokens} tokens</b>\n"

    # image generation
    image_generation_n_spent_dollars = config.models["info"]["dalle-2"]["price_per_1_image"] * n_generated_images
    if n_generated_images != 0:
        details_text += f"- DALL·E 2 (image generation): <b>{image_generation_n_spent_dollars:.03f}$</b> / <b>{n_generated_images} generated images</b>\n"

    total_n_spent_dollars += image_generation_n_spent_dollars

    # voice recognition
    voice_recognition_n_spent_dollars = config.models["info"]["whisper"]["price_per_1_min"] * (n_transcribed_seconds / 60)
    if n_transcribed_seconds != 0:
        details_text += f"- Whisper (voice recognition): <b>{voice_recognition_n_spent_dollars:.03f}$</b> / <b>{n_transcribed_seconds:.01f} seconds</b>\n"

    total_n_spent_dollars += voice_recognition_n_spent_dollars


    text = f"You spent <b>{total_n_spent_dollars:.03f}$</b>\n"
    text += f"You used <b>{total_n_used_tokens}</b> tokens\n\n"
    text += details_text

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def edited_message_handle(update: Update, context: CallbackContext):
    if update.edited_message.chat.type == "private":
        text = "🥲 Unfortunately, message <b>editing</b> is not supported"
        await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def error_handle(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        # collect error message
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # split text into multiple messages due to 4096 character limit
        for message_chunk in split_text_into_chunks(message, 4096):
            try:
                await context.bot.send_message(update.effective_chat.id, message_chunk, parse_mode=ParseMode.HTML)
            except telegram.error.BadRequest:
                # answer has invalid characters, so we send it without parse_mode
                await context.bot.send_message(update.effective_chat.id, message_chunk)
    except:
        await context.bot.send_message(update.effective_chat.id, "Some error in error handler")

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/new", "Start new dialog"),
        BotCommand("/mode", "Select chat mode"),
        BotCommand("/retry", "Re-generate response for previous query"),
        BotCommand("/search", "Search the web"),
        BotCommand("/balance", "Show balance"),
        BotCommand("/settings", "Show settings"),
        BotCommand("/help", "Show help message"),
    ])

def run_bot() -> None:
    application = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .concurrent_updates(True)
        .rate_limiter(AIORateLimiter(max_retries=5))
        .http_version("1.1")
        .get_updates_http_version("1.1")
        .post_init(post_init)
        .build()
    )

    # add handlers
    user_filter = filters.ALL
    if len(config.allowed_telegram_usernames) > 0:
        usernames = [x for x in config.allowed_telegram_usernames if isinstance(x, str)]
        any_ids = [x for x in config.allowed_telegram_usernames if isinstance(x, int)]
        user_ids = [x for x in any_ids if x > 0]
        group_ids = [x for x in any_ids if x < 0]
        user_filter = filters.User(username=usernames) | filters.User(user_id=user_ids) | filters.Chat(chat_id=group_ids)

    application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    application.add_handler(CommandHandler("help", help_handle, filters=user_filter))
    application.add_handler(CommandHandler("help_group_chat", help_group_chat_handle, filters=user_filter))
    application.add_handler(CommandHandler("search", search_handle, filters=user_filter))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, message_handle))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND & user_filter, message_handle))
    application.add_handler(MessageHandler(filters.VIDEO & ~filters.COMMAND & user_filter, unsupport_message_handle))
    application.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND & user_filter, unsupport_message_handle))
    application.add_handler(CommandHandler("retry", retry_handle, filters=user_filter))
    application.add_handler(CommandHandler("new", new_dialog_handle, filters=user_filter))
    application.add_handler(CommandHandler("cancel", cancel_handle, filters=user_filter))

    application.add_handler(MessageHandler(filters.VOICE & user_filter, voice_message_handle))

    application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(show_chat_modes_callback_handle, pattern="^show_chat_modes"))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))

    application.add_handler(CommandHandler("settings", settings_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_settings_handle, pattern="^set_settings"))

    application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))

    application.add_error_handler(error_handle)

    # start the bot
    application.run_polling()


if __name__ == "__main__":
    run_bot()
