import os
import random
import json
import threading
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Bot Configuration
TOKEN = "YOUR_BOT_TOKEN"  # Replace with your bot token
AUTHORIZED_USERS = []  # Replace with Telegram user IDs who can upload images
AUTHORIZED_GROUP_ID =   # Replace with your group ID

# File paths for storing data
IMAGES_FILE = "images.json"
USERS_FILE = "users.json"

# Load or initialize data from JSON files
if os.path.exists(IMAGES_FILE):
    with open(IMAGES_FILE, "r") as f:
        images = json.load(f)
else:
    images = {}

if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

# Game state variables
current_game = None  # Stores the current game character
game_timer = None  # Timer for auto-ending the game


def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)


def save_images():
    with open(IMAGES_FILE, "w") as f:
        json.dump(images, f)


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


def qdelete(update: Update, context: CallbackContext) -> None:
    """Delete an uploaded anime character image."""
    if not context.args:
        update.message.reply_text("Usage: /qdelete CharacterName (e.g., /qdelete Sasuke-Uchiha).")
        return

    character_name = " ".join(context.args)
    filename = f"{character_name.replace(' ', '_')}.jpg"

    if filename in images:
        del images[filename]
        save_images()
        update.message.reply_text(f"Deleted image for {character_name}.")
    else:
        update.message.reply_text(f"No image found for {character_name}.")


def qupdate(update: Update, context: CallbackContext) -> None:
    """Update an uploaded anime character image."""
    if not context.args or not update.message.reply_to_message or not update.message.reply_to_message.photo:
        update.message.reply_text("Usage: /qupdate CharacterName (while replying to an image).")
        return

    character_name = " ".join(context.args)
    filename = f"{character_name.replace(' ', '_')}.jpg"

    if filename in images:
        # Delete old image and update with new one
        file = update.message.reply_to_message.photo[-1].get_file()
        file_path = f"images/{filename}"
        file.download(file_path)

        images[filename] = character_name
        save_images()

        update.message.reply_text(f"Updated image for {character_name}!")
    else:
        update.message.reply_text(f"No image found for {character_name}. Upload a new one using /upload first.")


def main():
    """Start the bot."""
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("upload", upload, pass_args=True))
    dp.add_handler(CommandHandler("guess", guess))
    dp.add_handler(CommandHandler("name", reveal_name))
    dp.add_handler(CommandHandler("qdelete", qdelete, pass_args=True))
    dp.add_handler(CommandHandler("qupdate", qupdate, pass_args=True))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, check_guess))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
