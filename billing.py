import sqlite3
import logging
from telebot import TeleBot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton


class PaymentStorage:
    def __init__(self, db_name='payments.db'):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER,
             charge_id TEXT,
             amount INTEGER,
             currency TEXT,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        ''')
        self.conn.commit()

    def store_payment(self, user_id, charge_id, amount, currency):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO payments (user_id, charge_id, amount, currency)
            VALUES (?, ?, ?, ?)
        ''', (user_id, charge_id, amount, currency))
        self.conn.commit()

    def get_payment(self, charge_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM payments WHERE charge_id = ?', (charge_id,))
        return cursor.fetchone()

    def get_user_balance(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT SUM(amount) FROM payments WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0


class BillingManager:
    def __init__(self, bot: TeleBot):
        self.bot = bot
        self.price = 1  # Price in Telegram Stars
        self.storage = PaymentStorage()
        self.logger = logging.getLogger('BillingManager')
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def send_invoice(self, chat_id):
        title = "Bot Feature Access"
        description = "Access to premium bot features"
        payload = f"access_{chat_id}"
        currency = "XTR"
        prices = [LabeledPrice(label="Bot Access", amount=self.price)]

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Pay", pay=True))

        self.bot.send_invoice(
            chat_id,
            title,
            description,
            payload,
            "",  # provider_token is empty for digital goods
            currency,
            prices,
            is_flexible=False,
            start_parameter="access",
            reply_markup=keyboard
        )

    def process_pre_checkout_query(self, pre_checkout_query):
        self.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

    def process_successful_payment(self, message):
        chat_id = message.chat.id
        payment_info = message.successful_payment
        charge_id = payment_info.telegram_payment_charge_id
        
        # Store payment information
        self.storage.store_payment(
            chat_id,
            charge_id,
            payment_info.total_amount,
            payment_info.currency
        )
        
        # Log the successful payment
        self.logger.info(f"Successful payment received. User ID: {chat_id}, Charge ID: {charge_id}")
        
        # Here you would typically update the user's access in your database
        self.bot.send_message(chat_id, "Payment successful! You now have access to premium features.")

    def get_user_balance(self, user_id):
        balance = self.storage.get_user_balance(user_id)
        return balance

    def handle_update(self, update):
        # import ipdb; ipdb.set_trace()
        if hasattr(update, 'pre_checkout_query') and update.pre_checkout_query:
            self.process_pre_checkout_query(update.pre_checkout_query)
        elif hasattr(update, 'message') and hasattr(update.message, 'successful_payment') and update.message.successful_payment:
            self.process_successful_payment(update.message)


# Usage example:
# billing_manager = BillingManager(bot)
# billing_manager.send_invoice(chat_id)
# In your main update handler:
# billing_manager.handle_update(update)
