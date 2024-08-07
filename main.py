import os
import requests
import telebot
from openai import OpenAI
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# OpenAI API Key
OPENAI_API_KEY = os.getenv('GPT4_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

def get_message_content(message):
    if message.content_type == 'text':
        return message.text[:100] + ('...' if len(message.text) > 100 else '')
    elif message.content_type == 'voice':
        return f"Voice message (duration: {message.voice.duration}s)"
    else:
        return f"{message.content_type} content"


def handle_voice(message):
    logging.info(f"Processing business voice message with connection ID: {message.business_connection_id}")
    try:
        # Check if it's a business message
        if not hasattr(message, 'business_connection_id'):
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
            logging.info(f"Transcription successful: {text}")
            
            # Send transcription back to the business chat
            bot.send_message(
                message.chat.id, 
                f"Transcription: {text}",
                business_connection_id=message.business_connection_id
            )
        else:
            bot.send_message(
                message.chat.id, 
                "Failed to transcribe voice message.",
                business_connection_id=message.business_connection_id
            )

    except Exception as e:
        logging.exception(f"An error occurred: {e}")
        bot.send_message(
            message.chat.id, 
            f"An error occurred: {e}",
            business_connection_id=message.business_connection_id
        )

    finally:
        # Clean up the temporary file
        if os.path.exists("voice.ogg"):
            os.remove("voice.ogg")

def handle_business_update(update):
    if not hasattr(update, 'business_message'):
        return
    message = update.business_message
    
    if not hasattr(message, "from_user"):
        return
    # user = message.from_user
    # username = user.username or f"{user.first_name} {user.last_name}".strip()
    
    # log_message = (
    #     f"Update Type: business_message\n"
    #     f"User: {username} (ID: {user.id})\n"
    #     f"Chat ID: {message.chat.id}\n"
    #     f"Content Type: {message.content_type}\n"
    #     f"Content: {get_message_content(message)}"
    # )
    # logging.info(log_message)
    
    if message.content_type == 'voice':
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
                    'message',
                    'edited_message',
                    'business_message',
                    'edited_business_message',
                    'deleted_business_messages',
                    'business_connection'
                ]
            )
            for update in updates:
                logging.info(f"Processing update ID: {update.update_id}")
                handle_business_update(update)
                offset = update.update_id + 1
        except Exception as e:
            logging.error(f"Error in polling loop: {e}")
            continue


@bot.message_handler(func=lambda message: True)
def log_all_messages(message):
    logging.info(f"Received message from user {message.from_user.id} in chat {message.chat.id}: {message.text}")


if __name__ == "__main__":
    logging.info("Bot started polling")
    custom_polling()