import os
import requests
from dotenv import load_dotenv

load_dotenv()

if os.getenv("TEST"):
    from telebot import apihelper
    apihelper.API_URL = 'https://api.telegram.org/bot{0}/test/{1}'
    apihelper.FILE_URL = 'https://api.telegram.org/bot{0}/test/{1}'

from io import BytesIO
import telebot
from openai import OpenAI
import logging
from ast import literal_eval

from billing import BillingManager  # Import the new BillingManager




logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

ALLOWED_BID_CONNECTIONS = set(literal_eval(os.getenv("ALLOWED_BID_CONNECTIONS", "[]")))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if os.getenv("TEST"):
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_TEST")

OPENAI_API_KEY = os.getenv("GPT4_API_KEY")
GPT_MODEL = "gpt-4o-2024-08-06"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

IMPROVEMENT_PROMPT = """Do not reply, do not comment. Just do you job. You will edit transcription of the audio file to text in its original language, splitting the copy into logical paragraphs based on pauses and topic changes. I will tip you for 100$ if you follow the rules: Do not start conversation. YOU SHOULD NEVER CHANGE WORDING AND PHRASEES. DO NOT HALUCINATE. DO NOT TREAT THIS AS CONVERSATION AND DO NOT REPLY FOR THE MESSAGES, Just edit it and provide response. The goal is to produce a clean, natural-sounding written version, but close to the original copy, free of unnecessary sounds and verbal clutter! Remove all filler words like "um," "uh," "like," "so,", "ahh," "er," "hmm," "ehh," "mmm," "uh-huh," and any similar sounds that don't contribute to the meaning. Also remove any non-speech sounds like throat clearing, lip smacking, and breaths. Remove repeated words or phrases caused by stuttering or hesitation. If the speaker makes a false start, transcribe only the final, corrected sentence. For example, "Uh... so, I was, um, thinking... like maybe we could... uh... you know... meet... meet up on Tuesday?" should become "I was thinking maybe we could meet up on Tuesday." Preserve the original meaning and avoid paraphrasing. Ensure the text flows naturally and is easy to read, like a written message. Accurately edit in the original language. Pay attention to natural breaks in the audio and split the transcription into paragraphs accordingly, creating a well-structured and readable final text. Your goal is a clean, concise, and easily understandable transcription that reflects the speaker's intended message. The first message in the chat will be the transcription."""

billing_manager = BillingManager(bot)


def validate_business_connection(connection_id):
    return connection_id in ALLOWED_BID_CONNECTIONS


def get_message_content(message):
    if message.content_type == "text":
        return message.text[:200] + ("..." if len(message.text) > 200 else "")
    elif message.content_type == "voice":
        return f"Voice message (duration: {message.voice.duration}s)"
    else:
        return f"{message.content_type} content"


def improve_transcription(transcription):
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": IMPROVEMENT_PROMPT},
            {"role": "user", "content": transcription},
        ],
    )
    return response.choices[0].message.content


def handle_voice(message, is_group_chat=False):
    try:
        if message.business_connection_id:
            logging.info(
                f"Processing business voice message with connection ID: {message.business_connection_id}"
            )
            if not validate_business_connection(message.business_connection_id):
                return

        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Use BytesIO instead of creating a real file
        voice_file = BytesIO(downloaded_file)
        voice_file.name = "voice.ogg"  # Set a name for the file-like object

        # Transcribe using Whisper API
        transcription_response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            data={"model": "whisper-1"},
            files={"file": voice_file},
        )

        if transcription_response.status_code == 200:
            transcription_result = transcription_response.json()
            text = transcription_result.get("text", "")
            improved_transcription = improve_transcription(text)

            logging.info(f"Transcription successful: {text}")
            logging.info(f"Enhanced message: {improved_transcription}")

            if is_group_chat:
                sender = (
                    message.from_user.username
                    or f"{message.from_user.first_name} {message.from_user.last_name}".strip()
                    if hasattr(message, "from_user")
                    else ""
                )
                title = f"*Voice message transcription from {sender} (thanks to bot created by @denyamsk)*"
            else:
                user = message.from_user if hasattr(message, "from_user") else message.chat
                username = user.username or f"{user.first_name} {user.last_name}".strip()
                title = f"*Voice message transcription from {username} (thanks to bot created by @denyamsk)*"

            # Send transcription back to the business chat
            bot.send_message(
                message.chat.id,
                f"{title}\n{improved_transcription}",
                business_connection_id=getattr(message, "business_connection_id", None),
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                message.chat.id,
                "Failed to transcribe voice message.",
                business_connection_id=getattr(message, "business_connection_id", None),
            )

    except Exception as e:
        logging.exception(f"An error occurred: {e}")
        bot.send_message(
            message.chat.id,
            f"An error occurred: {e}",
            business_connection_id=getattr(message, "business_connection_id", None),
            parse_mode="Markdown",
        )


def handle_business_update(update):
    if update.business_message:
        message = update.business_message

    if not message:
        return

    direction = "incoming" if hasattr(message, "from_user") else "outgoing"
    user = message.from_user if hasattr(message, "from_user") else message.chat
    username = user.username or f"{user.first_name} {user.last_name}".strip()

    log_message = f"{direction.capitalize()} business message - User: {username} (ID: {user.id}), Chat ID: {message.chat.id}, Type: {message.content_type}, Content: {get_message_content(message)}"
    logging.info(log_message)

    if message.content_type == "voice":
        handle_voice(message)

    # elif update_type == 'business_connection':
    #     logging.info(f"Business Connection Update: {update_content.status}")
    # elif update_type == 'deleted_business_messages':
    #     logging.info(f"Deleted Business Messages: {update_content.deleted_message_ids}")
    # else:
    #     logging.info(f"Received {update_type} update")


@bot.message_handler(chat_types=["group", "supergroup"], content_types=["voice"])
def handle_group_chat_message(message):
    logging.info("Handling voice in the group chat")
    if message.content_type == "voice":
        handle_voice(message, is_group_chat=True)


@bot.message_handler(commands=['pay'])
def pay_command(message):
    billing_manager.send_invoice(message.chat.id)


@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    billing_manager.process_pre_checkout_query(pre_checkout_query)


@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    billing_manager.process_successful_payment(message)

@bot.message_handler(func=lambda message: True)
def log_all_messages(message):
    logging.info(
        f"Regular message - User: {message.from_user.username or message.from_user.first_name} (ID: {message.from_user.id}), Chat ID: {message.chat.id}, Content: {get_message_content(message)}"
    )


def process_updates(updates):
    for update in updates:
        if update.business_message:
            handle_business_update(update)
        else:
            bot.process_new_updates([update])


def custom_polling():
    offset = 0
    while True:
        try:
            updates = bot.get_updates(
                offset=offset,
                timeout=30,
                allowed_updates=[
                    "message",
                    "edited_message",
                    "business_message",
                    "edited_business_message",
                    "deleted_business_messages",
                    "business_connection",
                    "pre_checkout_query",
                    "successful_payment",
                ],
            )
            if updates:
                offset = updates[-1].update_id + 1
                process_updates(updates)

        except Exception as e:
            logging.exception(f"Error in polling loop: {e}")
            continue


if __name__ == "__main__":
    logging.info("Bot started polling")
    custom_polling()
