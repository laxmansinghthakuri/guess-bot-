import os
import random
import threading
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from pymongo import MongoClient

# Bot Configuration
TOKEN = "8115321734:AAE6L_cxrunhb3rsv_oivFVoUQTCVrtLbrc"
MONGO_URI = "mongodb+srv://shivva0560:Ch9WKTOcnaEbAMof@cluster0.sultr.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
AUTHORIZED_USERS = [6442844937] [6806897901]  # Replace with authorized user IDs
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

def guess(update: Update, context: CallbackContext) -> None:
    """Start a new guessing game."""
    global current_game, game_timer

    if update.message.chat_id != AUTHORIZED_GROUP_ID:
        return  # Silent for unauthorized groups

    if current_game:
        # Inform the user that a game is already in progress
        update.message.reply_text("A guess is already in progress. Please wait until it's completed.")
        return  # Silent if a game is already in progress

    if not images:
        update.message.reply_text("No images available. Admins need to upload using /upload.")
        return

    filename = random.choice(list(images.keys()))
    character_name = images[filename]

    current_game = {
        "character_name": character_name.lower(),
        "filename": filename,
        "start_time": datetime.now()
    }

    with open(f"images/{filename}", "rb") as photo:
        update.message.reply_photo(photo, caption="Who is this Mysterious character! 🤔🧐?")

    # Start a 20-second timer to terminate the game
    game_timer = threading.Timer(20, end_game, [context])
    game_timer.start()

def end_game(context: CallbackContext):
    """End the current game after 20 seconds."""
    global current_game
    if current_game:
        context.bot.send_message(AUTHORIZED_GROUP_ID, "Time's up! No one guessed correctly.")
        current_game = None


def check_guess(update: Update, context: CallbackContext) -> None:
    """Check if the user's guess is correct."""
    global current_game, game_timer

    if not current_game:
        return  # Silent if no game is in progress

    user_guess = update.message.text.lower()
    correct_name = current_game["character_name"]

    name_parts = correct_name.split("-")
    valid_answers = {name_parts[0], name_parts[1]} if len(name_parts) == 2 else {correct_name}

    if user_guess in valid_answers:
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "Unknown"

        if user_id not in users:
            users[user_id] = {"username": username, "bitcoin": 0, "correct_guesses": 0}

        user_data = users[user_id]
        user_data["correct_guesses"] += 1
        earned_bitcoin = 100  # Bitcoin reward per correct guess
        user_data["bitcoin"] += earned_bitcoin

        save_users()
        update.message.reply_text(f"🎉 Correct! You earned {earned_bitcoin} Bitcoin!" )
        # Stop the game and allow a new one
        current_game = None
        if game_timer:
            game_timer.cancel()
    else:
        return  # Silent on incorrect guesses

def reveal_name(update: Update, context: CallbackContext) -> None:
    """Reveal the name of the currently spawned character."""
    if not current_game:
        update.message.reply_text("No game is currently running.")
        return

    update.message.reply_text(f"The character is: {current_game['character_name'].capitalize()}")

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

        await update.message.reply_text(f"🎉 Correct! The character is {correct_name.replace('-', ' ').capitalize()}. You earned 100 Bitcoin!")

        # Transfer Bitcoin to @SeizeXhusbando_bot
        transfer_bitcoin(user_id, 100)

        # Reset the game
        current_game = None
        if game_timer:
            game_timer.cancel()
    else:
        return  # Silent if the guess is incorrect

async def upload_character(update: Update, context: CallbackContext):
def upload(update: Update, context: CallbackContext) -> None:
    """Upload an anime character image (only authorized users)."""
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        update.message.reply_text("You are not authorized to upload images.")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        update.message.reply_text("Reply to an image with the format: `/upload FirstName-Surname`")
        return

    if not context.args:
        update.message.reply_text("Usage: /upload FirstName-Surname (while replying to an image).")
        return

    character_name = " ".join(context.args)
    if "-" not in character_name:
        update.message.reply_text("Format should be: `FirstName-Surname` (Example: Sasuke-Uchiha).")
        return

    file = update.message.reply_to_message.photo[-1].get_file()
    filename = f"{character_name.replace(' ', '_')}.jpg"
    file_path = f"images/{filename}"

    os.makedirs("images", exist_ok=True)
    file.download(file_path)

    images[filename] = character_name
    save_images()

    update.message.reply_text(f"Uploaded image for {character_name}!")

    # Download and save the image
    await photo.get_file().download_to_drive(file_path)

    # Save character to MongoDB
    characters_collection.insert_one({"name": character_name, "image_path": file_path})
    await update.message.reply_text(f"Character '{character_name.replace('-', ' ').capitalize()}' has been uploaded successfully!")

def main():
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("guess", start_game))
    application.add_handler(CommandHandler("upload", upload_character))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_guess))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
