import os
import requests
import telebot
from openai import OpenAI
import logging
from dotenv import load_dotenv
from ast import literal_eval


load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

ALLOWED_BID_CONNECTIONS = set(literal_eval(os.getenv("ALLOWED_BID_CONNECTIONS", "[]")))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("GPT4_API_KEY")
GPT_MODEL = "gpt-4o-mini"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

IMPROVEMENT_PROMPT = """You will edit transcription of the audio file to text in its original language, splitting the copy into logical paragraphs based on pauses and topic changes. YOU SHOULD NEVER CHANGE WORDING AND PHRASEES. DO NOT HALUCINATE. The goal is to produce a clean, natural-sounding written version, but close to the original copy, free of unnecessary sounds and verbal clutter!  Remove all filler words like "um," "uh," "like," "so,", "ahh," "er," "hmm," "ehh," "mmm," "uh-huh," and any similar sounds that don't contribute to the meaning. Also remove any non-speech sounds like throat clearing, lip smacking, and breaths. Remove repeated words or phrases caused by stuttering or hesitation. If the speaker makes a false start, transcribe only the final, corrected sentence. For example, "Uh... so, I was, um, thinking... like maybe we could... uh... you know... meet... meet up on Tuesday?" should become "I was thinking maybe we could meet up on Tuesday."  Preserve the original meaning and avoid paraphrasing. Ensure the text flows naturally and is easy to read, like a written message. Accurately edit in the original language. Pay attention to natural breaks in the audio and split the transcription into paragraphs accordingly, creating a well-structured and readable final text. Your goal is a clean, concise, and easily understandable transcription that reflects the speaker's intended message. """


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
        # Check if it's a business message
        # if not hasattr(message, 'business_connection_id'):
        #     return

        if message.business_connection_id:
            logging.info(
                f"Processing business voice message with connection ID: {message.business_connection_id}"
            )
            if not validate_business_connection(message.business_connection_id):
                return

        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Save the voice message temporarily
        with open("voice.ogg", "wb") as new_file:
            new_file.write(downloaded_file)

        # Transcribe using Whisper API
        transcription_response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            data={"model": "whisper-1"},
            files={"file": open("voice.ogg", "rb")},
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

    finally:
        if os.path.exists("voice.ogg"):
            os.remove("voice.ogg")


def handle_business_update(update):
    if update.business_message:
        message = update.business_message
    else:
        message = update.message

    if not message:
        return

    direction = "incoming" if hasattr(message, "from_user") else "outgoing"
    user = message.from_user if hasattr(message, "from_user") else message.chat
    username = user.username or f"{user.first_name} {user.last_name}".strip()

    log_message = f"{direction.capitalize()} business message - User: {username} (ID: {user.id}), Chat ID: {message.chat.id}, Type: {message.content_type}, Content: {get_message_content(message)}"
    logging.info(log_message)

    if message.content_type == "voice" and message.chat.type in ["group", "supergroup"]:
        logging.info("Handling voice in the group chat")
        handle_voice(message, is_group_chat=True)
    elif message.content_type == "voice":
        handle_voice(message)

    # elif update_type == 'business_connection':
    #     logging.info(f"Business Connection Update: {update_content.status}")
    # elif update_type == 'deleted_business_messages':
    #     logging.info(f"Deleted Business Messages: {update_content.deleted_message_ids}")
    # else:
    #     logging.info(f"Received {update_type} update")


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
                ],
            )
            for update in updates:
                handle_business_update(update)
                offset = update.update_id + 1
        except Exception as e:
            logging.exception(f"Error in polling loop: {e}")
            continue


@bot.message_handler(func=lambda message: True)
def log_all_messages(message):
    logging.info(
        f"Regular message - User: {message.from_user.username or message.from_user.first_name} (ID: {message.from_user.id}), Chat ID: {message.chat.id}, Content: {get_message_content(message)}"
    )


if __name__ == "__main__":
    logging.info("Bot started polling")
    custom_polling()
