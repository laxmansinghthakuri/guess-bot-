import os
import random
import threading
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext
from pymongo import MongoClient

# Bot Configuration
TOKEN = "8115321734:AAE6L_cxrunhb3rsv_oivFVoUQTCVrtLbrc"
MONGO_URI = "mongodb+srv://shivva0560:Ch9WKTOcnaEbAMof@cluster0.sultr.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
AUTHORIZED_USERS = [6442844937]  # Replace with authorized user IDs
AUTHORIZED_GROUP_ID = -1002368559724  # Replace with your group ID

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["game_database"]
users_collection = db["users"]
characters_collection = db["characters"]

# Game state variables
current_game = None  # Stores the current game character
game_timer = None  # Timer for auto-ending the game

def transfer_bitcoin(user_id, amount):
    """Transfer Bitcoin from @NarutoXgameBot to @SeizeXhusbando_bot."""
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data or user_data["Bitcoin"] < amount:
        return  # Not enough balance

    # Deduct from @NarutoXgameBot
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"Bitcoin": -amount}}
    )

    # Add to @SeizeXhusbando_bot (same database)
    seize_user = users_collection.find_one({"user_id": user_id, "bot": "seize"})
    if seize_user:
        users_collection.update_one(
            {"user_id": user_id, "bot": "seize"},
            {"$inc": {"Bitcoin": amount}}
        )
    else:
        users_collection.insert_one(
            {"user_id": user_id, "bot": "seize", "Bitcoin": amount}
        )

def start_game(update: Update, context: CallbackContext) -> None:
    """Start a new game with a random character."""
    global current_game, game_timer

    if update.message.chat_id != AUTHORIZED_GROUP_ID:
        return

    if current_game:
        update.message.reply_text("A game is already running. Wait for it to end.")
        return

    # Fetch random character from MongoDB
    character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
    current_game = {
        "character_name": character["name"].lower(),
        "start_time": datetime.now()
    }

    with open(character["image_path"], "rb") as photo:
        update.message.reply_photo(photo, caption="Who is this Mysterious character? 🤔")

    # Start a 20-second timer for game timeout
    game_timer = threading.Timer(20, game_timeout, [context])
    game_timer.start()

def game_timeout(context: CallbackContext) -> None:
    """End the current game if no one guesses correctly."""
    global current_game
    if current_game:
        context.bot.send_message(AUTHORIZED_GROUP_ID, "Time's up! No one guessed correctly.")
        current_game = None

def check_guess(update: Update, context: CallbackContext) -> None:
    """Check if the user's guess is correct."""
    global current_game, game_timer

    if not current_game:
        return  # No game in progress

    user_guess = update.message.text.lower()
    correct_name = current_game["character_name"]

    if user_guess in correct_name:
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "Unknown"

        # Update user data in MongoDB
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data:
            users_collection.insert_one({"user_id": user_id, "username": username, "Bitcoin": 0, "correct_guesses": 0})

        # Reward user with Bitcoin and update stats
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"correct_guesses": 1, "Bitcoin": 100}}
        )

        update.message.reply_text(f"🎉 Correct! The character is {correct_name.replace('-', ' ').capitalize()}. You earned 100 Bitcoin!")

        # Transfer Bitcoin to @SeizeXhusbando_bot
        transfer_bitcoin(user_id, 100)

        # Reset the game
        current_game = None
        if game_timer:
            game_timer.cancel()
    else:
        return  # Silent if the guess is incorrect

def upload_character(update: Update, context: CallbackContext) -> None:
    """Allow authorized users to upload a new character."""
    if update.message.from_user.id not in AUTHORIZED_USERS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        update.message.reply_text("You must reply to an image with the character's name. Format: /upload <character_name>")
        return

    if not context.args or len(context.args) < 1:
        update.message.reply_text("Usage: /upload <character_name>")
        return

    character_name = context.args[0].lower()
    photo = update.message.reply_to_message.photo[-1]
    file_path = f"images/{character_name}.jpg"

    # Download and save the image
    photo.get_file().download(file_path)

    # Save character to MongoDB
    characters_collection.insert_one({"name": character_name, "image_path": file_path})
    update.message.reply_text(f"Character '{character_name.replace('-', ' ').capitalize()}' has been uploaded successfully!")

def main() -> None:
    """Start the bot."""
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("guess", start_game))
    dp.add_handler(CommandHandler("upload", upload_character))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, check_guess))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
