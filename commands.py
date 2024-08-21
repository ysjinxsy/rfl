import nextcord
from nextcord.ext import commands 
from nextcord import Interaction, SelectOption, ui, SlashOption, TextInputStyle, ChannelType, File
from nextcord.ui import Button, View, Modal, TextInput, RoleSelect, ChannelSelect, Select
import aiosqlite 
import re
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import io
from nextcord.utils import utcnow 
from db import get_config, get_teams
import logging
import aiohttp
import datetime
from shared import guild_id
from datetime import datetime
import requests
import functools
import random
import time
import asyncio
logging.basicConfig(
    level=logging.INFO,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log message format
    handlers=[
        logging.StreamHandler()          # Log to console
    ]
)
ADMIN_USER_IDS = [1211365819054030960]  
intents = nextcord.Intents.all()
guild_id = 1121488773247684618
client = commands.Bot(command_prefix="?", intents=intents, help_command=None)
DATABASE_PATH = "soccer_cards.db"

def format_number(number):
    return f"{number:,}"


@client.slash_command(name="addcard", description="Add a new card to the database.", guild_ids=[guild_id])
async def addcard(
    interaction: Interaction,
    name: str = SlashOption(description="Card name"),
    ovrate: int = SlashOption(description="Overall rating of the player"),
    position: str = SlashOption(description="Position of the player"),
    price: int = SlashOption(description="Price of the card"),
    country: str = SlashOption(description="Country of the player"),
    club: str = SlashOption(description="Club of the player"),
    image_attachment: nextcord.Attachment = SlashOption(description="Image attachment of the player's image")
):
    
    if interaction.user.id not in ADMIN_USER_IDS:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    

    await interaction.response.defer()  # Defer the interaction to avoid timeout

    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            image_data = await image_attachment.read()
            image_buffer = io.BytesIO(image_data)

            # Convert the image data to a BLOB for storage in the database
            await db.execute('''
                INSERT INTO cards (name, ovrate, position, price, country, club, image_blob)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, ovrate, position, price, country, club, image_buffer.getvalue()))
            
            await db.commit()
            await interaction.followup.send(f"{name} with overall rating {ovrate} and position {position} has been added to the database!")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")



CHEMISTRY_IMAGES_URLS = {
    'green': "https://cdn.discordapp.com/attachments/1187893488763805750/1275752068757590046/green.png?ex=66c70833&is=66c5b6b3&hm=8cb7b6fa212a65526c6d42548c68465f6d6903ec5d66905adcea20468b9536fc&",
    'orange': "https://cdn.discordapp.com/attachments/1187893488763805750/1275752068417716235/yellow.png?ex=66c70833&is=66c5b6b3&hm=7c60c0e2c57cc02a3445a618d2a742f4e53af637d36edad823e753e721b0a46a&",
    'red': "https://cdn.discordapp.com/attachments/1187893488763805750/1275752069126557810/red.png?ex=66c70833&is=66c5b6b3&hm=ddb0452a63360c2da929f76e47e5e435b792b62e2e29fd884fc4bf93d076b3aa&"
}

def calculate_chemistry(cards):
    clubs = {}
    countries = {}

    for card in cards:
        _, _, _, _, club, country, _ = card
        clubs[club] = clubs.get(club, 0) + 1
        countries[country] = countries.get(country, 0) + 1

    max_club_chemistry = max(clubs.values(), default=0)
    max_country_chemistry = max(countries.values(), default=0)

    chemistry = max_club_chemistry + max_country_chemistry

    if max_club_chemistry >= 5 or max_country_chemistry >= 5:
        level = 'green'
    elif max_club_chemistry >= 3 or max_country_chemistry >= 3:
        level = 'orange'
    else:
        level = 'red'

    return chemistry, level

# Function to download image data from a URL
async def download_image(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download image from {url}")
            return await response.read()

# Main slash command function
@client.slash_command(name="lineup", description="View your card collection in a lineup image.", guild_ids=[guild_id])
async def lineup(interaction: nextcord.Interaction):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    username = interaction.user.name

    try:
        # Fetch cards from the user's lineup
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute('''
                SELECT cards.name, cards.position, cards.ovrate, cards.price, cards.club, cards.country, cards.image_blob
                FROM cards
                INNER JOIN user_lineups ON cards.id = user_lineups.card_id
                WHERE user_lineups.user_id = ?
            ''', (user_id,)) as cursor:
                cards = await cursor.fetchall()

        if not cards:
            await interaction.followup.send("You don't have any cards in your lineup yet.")
            return

        chemistry, level = calculate_chemistry(cards)

        # Calculate OVR RATING and OVR VALUE
        total_ovr = sum(card[2] for card in cards)
        total_value = sum(card[3] for card in cards)

        # Load background image
        background_url = "https://cdn.discordapp.com/attachments/1224847916750082058/1275747929612746795/lineupahh.png?ex=66c70458&is=66c5b2d8&hm=38d20c0e2a73b00232102caa1f8d906b170467edd5192aa20118bdea4d139960&"
        background_image_data = await download_image(background_url)
        background_image = Image.open(io.BytesIO(background_image_data))

        # Download and resize chemistry level images
        chemistry_images = {}
        for level_name, url in CHEMISTRY_IMAGES_URLS.items():
            image_data = await download_image(url)
            chemistry_images[level_name] = Image.open(io.BytesIO(image_data)).resize((25, 25))

        # Create the lineup image
        lineup_image = create_lineup_image(background_image, cards, total_ovr, total_value, username, chemistry_images[level])

        # Save and send the lineup image
        await send_lineup_image(interaction, lineup_image)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")

# Function to create the lineup image
def create_lineup_image(background_image, cards, total_ovr, total_value, username, chemistry_image):
    lineup_width, lineup_height = 892, 725
    card_width, card_height = 110, 155

    lineup_image = background_image.resize((lineup_width, lineup_height))
    draw = ImageDraw.Draw(lineup_image)

    # Load custom font
    font_path = "FFGoodProCond-Black.ttf"  # Update with your font file path
    font = ImageFont.truetype(font_path, 24)

    # Add OVR RATING, OVR VALUE, and Chemistry text
    draw.text((120, 8), "OVR RATING:", font=font, fill="black")
    draw.text((125, 27), f"{total_ovr}", font=font, fill="black")
    draw.text((264, 8), "OVR VALUE:", font=font, fill="black")
    draw.text((270, 27), f"{format_number(total_value)}", font=font, fill="black")
    draw.text((656, 13), "Chemistry:", font=font, fill="black")
    draw.text((459, 13), f"{username}", font=font, fill="black")

    # Overlay the chemistry level image
    lineup_image.paste(chemistry_image, (746, 12), chemistry_image.convert("RGBA"))

    position_coords = {
        'ST': (395, 72),
        'CAM': (395, 220),
        'GK': (395, 516),
        'LW': (170, 111),
        'RW': (620, 111),
        'CB': (395, 368),
        'RB': (569, 368),
        'LB': (221, 368)
    }

    for card in cards:
        name, position, ovr, price, club, country, image_blob = card
        coords = position_coords.get(position, (0, 0))

        card_image = Image.open(io.BytesIO(image_blob)).resize((card_width, card_height))
        lineup_image.paste(card_image, coords, card_image.convert("RGBA"))

    return lineup_image

# Function to save and send the lineup image
async def send_lineup_image(interaction, lineup_image):
    try:
        # Save the image to a temporary file
        file_path = "lineup_temp.png"
        lineup_image.save(file_path)

        # Send the file to Discord
        await interaction.followup.send("Here is your lineup image:", file=nextcord.File(file_path))

    finally:
        # Delete the temporary file after sending
        if os.path.exists(file_path):
            os.remove(file_path)

# Helper function to format numbers (e.g., OVR VALUE)
def format_number(value):
    return f"{value:,}"
@client.slash_command(name="balance", description="Check your current balance.", guild_ids=[guild_id])
async def balance(interaction: Interaction):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    user_name = interaction.user.display_name  # Get the user's display name

    async with aiosqlite.connect('soccer_cards.db') as db:
        try:
            # Fetch the user's balance
            async with db.execute('''
                SELECT balance
                FROM user_balances
                WHERE user_id = ?
            ''', (user_id,)) as cursor:
                result = await cursor.fetchone()

            if result:
                balance = result[0]

                # Fetch the card IDs from user_collections
                async with db.execute('''
                    SELECT card_id
                    FROM user_collections
                    WHERE user_id = ?
                ''', (user_id,)) as cursor:
                    card_ids = await cursor.fetchall()

                if not card_ids:
                    player_value = 0
                else:
                    # Extract card IDs
                    card_ids = [card_id[0] for card_id in card_ids]

                    # Fetch the values of the cards from the cards table
                    async with db.execute('''
                        SELECT SUM(price)
                        FROM cards
                        WHERE id IN ({seq})
                    '''.format(seq=','.join(['?'] * len(card_ids))), tuple(card_ids)) as cursor:
                        player_value_result = await cursor.fetchone()

                    player_value = player_value_result[0] if player_value_result[0] else 0
                
                sell_value = int(0.8 * player_value)
                embed = nextcord.Embed(description=f"{user_name} has a budget of  ``{format_number(balance)}``<:aifa:1275168935737557012> .")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("You don't have a balance record. Please check with the administrator.")

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")



@client.slash_command(name="view_cards", description="View all available cards for purchase and their prices.", guild_ids=[guild_id])
async def view_cards(interaction: Interaction):
    await interaction.response.defer()

    async with aiosqlite.connect('soccer_cards.db') as db:
        try:
            async with db.execute('''
                SELECT name, price
                FROM cards
            ''') as cursor:
                cards = await cursor.fetchall()

            if not cards:
                await interaction.followup.send("No cards are available for purchase at the moment.")
                return

            # Format the card list
            card_list = "\n".join([f"**{name}**: {format_number(price)} coins" for name, price in cards])
            
            # Send the response
            embed = nextcord.Embed(
                title='Available Cards',
                description=card_list  # You can choose any color you'd like
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")



@client.slash_command(name="club", description="Shows all players you have in your collection.", guild_ids=[guild_id])
async def club(interaction: Interaction):
    user_id = str(interaction.user.id)

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Fetch the cards in the user's collection along with their details
            async with db.execute('''
                SELECT cards.name, cards.position
                FROM cards 
                INNER JOIN user_collections ON cards.id = user_collections.card_id 
                WHERE user_collections.user_id = ?
            ''', (user_id,)) as cursor:
                cards = await cursor.fetchall()

            if not cards:
                await interaction.response.send_message("You don't have any cards yet.")
                return

            # Format the list of cards
            card_list = "\n".join([f"{name} - Position: {position}" for name, position in cards])
            await interaction.response.send_message(f"Your club:\n{card_list}")
            
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")




@client.slash_command(name="switch", description="Change the position of a player in your collection.", guild_ids=[guild_id])
async def switch(interaction: Interaction, card_name: str, new_position: str):
    user_id = str(interaction.user.id)

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Check if the card is in the user's collection
            async with db.execute('''
                SELECT card_id
                FROM user_collections
                INNER JOIN cards ON user_collections.card_id = cards.id
                WHERE cards.name = ? AND user_collections.user_id = ?
            ''', (card_name, user_id)) as cursor:
                result = await cursor.fetchone()

            if not result:
                await interaction.response.send_message("Card not found in your collection.")
                return

            card_id = result[0]

            # Check if the new position is available
            async with db.execute('''
                SELECT card_id
                FROM user_collections
                INNER JOIN cards ON user_collections.card_id = cards.id
                WHERE cards.position = ? AND user_collections.user_id = ?
            ''', (new_position, user_id)) as cursor:
                conflict_card = await cursor.fetchone()

            if conflict_card:
                await interaction.response.send_message(f"Position '{new_position}' is already occupied by another card.")
                return

            # Update the position of the card
            async with db.execute('''
                UPDATE cards
                SET position = ?
                WHERE id = ?
            ''', (new_position, card_id)):
                await db.commit()

            await interaction.response.send_message(f"Position of card '{card_name}' has been updated to '{new_position}'.")

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")




cooldown_end_times = {}
COOLDOWN_DURATION = 86400  # 24 hours in seconds


@client.slash_command(name="claim", description="Claim a random card and add it to your collection.", guild_ids=[guild_id])
async def claim(interaction: Interaction):
    user_id = str(interaction.user.id)
    current_time = time.time()  # Get current time in seconds
    
    # ID of the user who can bypass the cooldown
    BYPASS_USER_ID = 1211365819054030960 # Replace with the actual user ID

    # Check if the user is on cooldown and does not bypass it
    if user_id != BYPASS_USER_ID and user_id in cooldown_end_times:
        end_time = cooldown_end_times[user_id]
        if current_time < end_time:
            await interaction.response.send_message(
                f"You need to wait {end_time - current_time:.2f} seconds before using this command again.",
                ephemeral=True
            )
            return

    try:
        # Acknowledge the interaction
        await interaction.response.defer()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Get available cards
            async with db.execute('''
                SELECT cards.id AS card_id, cards.name, cards.ovrate, cards.position, cards.price, cards.country, cards.club, cards.image_blob
                FROM cards
                WHERE cards.id NOT IN (SELECT card_id FROM user_collections WHERE user_id = ?)
            ''', (user_id,)) as cursor:
                available_cards = await cursor.fetchall()

        if not available_cards:
            await interaction.followup.send("There are no available cards left to claim!")
            return

        # Create a list of cards with weights based on their OVR
        cards_with_weights = [(card, card[2]) for card in available_cards]  # (card, ovrate)
        total_weight = sum(weight for _, weight in cards_with_weights)

        # Choose a card based on weighted probability
        pick = random.uniform(0, total_weight)
        current = 0
        for card, weight in cards_with_weights:
            current += weight
            if current > pick:
                selected_card = card
                break

        card_id, card_name, ovrate, position, card_price, country, club, image_blob = selected_card

        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Check if user already owns this card
            async with db.execute('''
                SELECT COUNT(*)
                FROM user_collections
                WHERE user_id = ? AND card_id = ?
            ''', (user_id, card_id)) as cursor:
                already_owned = (await cursor.fetchone())[0] > 0

        view = nextcord.ui.View()

        if already_owned:
            # Provide only the sell button
            async def sell_card(interaction: Interaction):
                # Ensure only the original user can interact
                if interaction.user.id != int(user_id):
                    await interaction.response.send_message("This button is not for you!", ephemeral=True)
                    return

                try:
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        await db.execute('''
                            INSERT INTO user_balances (user_id, balance)
                            VALUES (?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
                        ''', (user_id, int(card_price * 0.8), int(card_price * 0.8)))
                        await db.commit()
                    await interaction.response.edit_message(content=f"You've sold the card '{card_name}' for :coin: {card_price} coins!", view=None)
                except Exception as e:
                    await interaction.response.edit_message(content=f"An error occurred: {e}", view=None)

            sell_button = nextcord.ui.Button(label="Sell", style=nextcord.ButtonStyle.gray, emoji="<:aifa:1275168935737557012>")
            sell_button.callback = sell_card
            view.add_item(sell_button)

            embed = nextcord.Embed(
                title=f"You already own {card_name}",
                description=f":coin: **Value:** ``{format_number(card_price)}`` coins **Sells for:** ``{format_number(int(card_price * 0.8))}`` coins"
            )
            embed.set_image(url=f"attachment://card_image.png")

        else:
            # Provide both claim and sell buttons
            async def claim_card(interaction: Interaction):
                # Ensure only the original user can interact
                if interaction.user.id != int(user_id):
                    await interaction.response.send_message("This button is not for you!", ephemeral=True)
                    return

                try:
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        await db.execute('INSERT INTO user_collections (user_id, card_id, position) VALUES (?, ?, ?)', (user_id, card_id, position))
                        await db.commit()
                    await interaction.response.edit_message(content=f"You've claimed the card '{card_name}'!", view=None)
                except Exception as e:
                    await interaction.response.edit_message(content=f"An error occurred: {e}", view=None)

            async def sell_card(interaction: Interaction):
                # Ensure only the original user can interact
                if interaction.user.id != int(user_id):
                    await interaction.response.send_message("This button is not for you!", ephemeral=True)
                    return

                try:
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        await db.execute('''
                            INSERT INTO user_balances (user_id, balance)
                            VALUES (?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
                        ''', (user_id, int(card_price * 0.8), int(card_price * 0.8)))
                        await db.commit()
                    await interaction.response.edit_message(content=f"You've sold the card '{card_name}' for :coin: {card_price} coins!", view=None)
                except Exception as e:
                    await interaction.response.edit_message(content=f"An error occurred: {e}", view=None)

            claim_button = nextcord.ui.Button(label="Add to Club", style=nextcord.ButtonStyle.gray, emoji="<:arrow:1275032436958433312>")
            claim_button.callback = claim_card

            sell_button = nextcord.ui.Button(label="Sell", style=nextcord.ButtonStyle.gray, emoji="<:aifa:1275168935737557012>")
            sell_button.callback = sell_card

            view.add_item(claim_button)
            view.add_item(sell_button)

            embed = nextcord.Embed(
                title=f"{card_name} joins your club",
                description=f':coin: **Value:** ``{format_number(card_price)}`` coins **Sells for:** ``{format_number(int(card_price * 0.8))}`` coins \n\n :coin: ``Quick Sell`` \n <:arrow:1275032436958433312> ``Add To Club``'
            )
            embed.set_image(url=f"attachment://card_image.png")

        await interaction.followup.send(embed=embed, view=view, files=[nextcord.File(fp=io.BytesIO(image_blob), filename="card_image.png")])

        # Set cooldown end time for the user
        if user_id != BYPASS_USER_ID:
            cooldown_end_times[user_id] = current_time + COOLDOWN_DURATION

        # Optionally, remove expired cooldowns periodically
        async def cleanup_expired_cooldowns():
            while True:
                await asyncio.sleep(COOLDOWN_DURATION)  # Sleep for the duration of the cooldown
                current_time = time.time()
                expired_users = [uid for uid, end_time in cooldown_end_times.items() if current_time >= end_time]
                for uid in expired_users:
                    cooldown_end_times.pop(uid, None)

        # Run the cleanup task in the background
        asyncio.create_task(cleanup_expired_cooldowns())

    except Exception as e:
        if interaction.response.is_done():
            await interaction.followup.send(f"An error occurred: {e}")
        else:
            await interaction.response.send_message(f"An error occurred: {e}")

@client.slash_command(name="delete_user_collection", description="Remove all cards from a user's collection (admin only).",guild_ids=[guild_id])
async def delete_user_collection(interaction: Interaction, user_id: str):
    if interaction.user.id not in ADMIN_USER_IDS:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Check if the user has any cards in their collection
            async with db.execute('''
                SELECT COUNT(*)
                FROM user_collections
                WHERE user_id = ?
            ''', (user_id,)) as cursor:
                count = await cursor.fetchone()

            if count[0] == 0:
                await interaction.response.send_message("The user does not have any cards in their collection.")
                return

            # Delete all cards from the user's collection
            async with db.execute('''
                DELETE FROM user_collections
                WHERE user_id = ?
            ''', (user_id,)):
                await db.commit()

            await interaction.response.send_message(f"All cards from user {user_id}'s collection have been removed.")

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")





@client.slash_command(name="8remove", description="Remove a card from your club by name, making it unavailable for your lineup.", guild_ids=[guild_id])
async def remove_from_club(interaction: Interaction, card_name: str):
    user_id = str(interaction.user.id)

    try:
        # Acknowledge the interaction
        await interaction.response.defer()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Check if the card exists by name
            async with db.execute('SELECT id FROM cards WHERE name = ?', (card_name,)) as cursor:
                card = await cursor.fetchone()

            if not card:
                await interaction.followup.send(f"Card with the name '{card_name}' does not exist.")
                return

            card_id = card[0]

            # Check if the user owns the card
            async with db.execute('SELECT * FROM user_clubs WHERE user_id = ? AND card_id = ?', (user_id, card_id)) as cursor:
                existing_card = await cursor.fetchone()

            if not existing_card:
                await interaction.followup.send(f"You do not have the card '{card_name}' in your club.")
                return

            # Remove the card from the user's club
            await db.execute('DELETE FROM user_clubs WHERE user_id = ? AND card_id = ?', (user_id, card_id))
            await db.commit()

        await interaction.followup.send(f"The card '{card_name}' has been successfully removed from your club and is no longer available for your lineup.")

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")


@client.slash_command(name="8add", description="Add a card from your club to your lineup by name.", guild_ids=[guild_id])
async def add_to_lineup(interaction: Interaction, card_name: str):
    user_id = str(interaction.user.id)

    try:
        # Acknowledge the interaction
        await interaction.response.defer()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Check if the card exists by name
            async with db.execute('SELECT id, position FROM cards WHERE name = ?', (card_name,)) as cursor:
                card = await cursor.fetchone()

            if not card:
                await interaction.followup.send(f"Card with the name '{card_name}' does not exist.")
                return

            card_id, card_position = card[0], card[1]

            # Check if the user owns the card in their collection
            async with db.execute('SELECT * FROM user_collections WHERE user_id = ? AND card_id = ?', (user_id, card_id)) as cursor:
                owned_card = await cursor.fetchone()

            if not owned_card:
                await interaction.followup.send(f"You do not own the card '{card_name}' in your club.")
                return

            # Check if the card is already in the user's lineup
            async with db.execute('SELECT * FROM user_lineups WHERE user_id = ? AND card_id = ?', (user_id, card_id)) as cursor:
                existing_lineup_card = await cursor.fetchone()

            if existing_lineup_card:
                await interaction.followup.send(f"The card '{card_name}' is already in your lineup.")
                return

            # Add the card to the user's lineup
            await db.execute('INSERT INTO user_lineups (user_id, card_id, position) VALUES (?, ?, ?)', (user_id, card_id, card_position))
            await db.commit()

        await interaction.followup.send(f"The card '{card_name}' has been successfully added to your lineup!")

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")









@client.slash_command(name="buy", description="Buy a card from the shop.", guild_ids=[guild_id])
async def buy(interaction: Interaction):
    await interaction.response.defer()

    user_id = str(interaction.user.id)

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Fetch all available cards
            async with db.execute('''
                SELECT id, name, price, ovrate, image_blob
                FROM cards
            ''') as cursor:
                cards = await cursor.fetchall()

            if not cards:
                await interaction.followup.send("No cards available in the shop.")
                return

        # Initialize the pagination
        current_index = 0
        total_cards = len(cards)

        async def update_embed(index):
            card_id, card_name, price, ovrate, image_blob = cards[index]

            embed = nextcord.Embed(
                title=f"{card_name} - OVR: {ovrate}",
                description=f"Price: {price} coins"
            )
            embed.set_image(url=f"attachment://card_image.png")

            return embed, nextcord.File(fp=io.BytesIO(image_blob), filename="card_image.png"), card_id, price

        # Create initial embed and buttons
        embed, image_file, current_card_id, current_price = await update_embed(current_index)
        
        view = nextcord.ui.View()

        async def previous_card(interaction: Interaction):
            nonlocal current_index, current_card_id, current_price
            if current_index > 0:
                current_index -= 1
            else:
                current_index = total_cards - 1
            
            embed, _, current_card_id, current_price = await update_embed(current_index)
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except nextcord.errors.NotFound:
                await interaction.followup.send(embed=embed, view=view)

        async def next_card(interaction: Interaction):
            nonlocal current_index, current_card_id, current_price
            if current_index < total_cards - 1:
                current_index += 1
            else:
                current_index = 0
            
            embed, _, current_card_id, current_price = await update_embed(current_index)
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except nextcord.errors.NotFound:
                await interaction.followup.send(embed=embed, view=view)

        async def buy_card(interaction: Interaction):
            nonlocal current_card_id, current_price
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Check if user has enough balance
                async with db.execute('''
                    SELECT balance
                    FROM user_balances
                    WHERE user_id = ?
                ''', (user_id,)) as cursor:
                    balance_result = await cursor.fetchone()

                if not balance_result:
                    await interaction.followup.send("User balance not found.")
                    return

                balance = balance_result[0]
                if balance < current_price:
                    await interaction.response.send_message("Insufficient balance.", ephemeral=True)
                    return

                # Add card to the user's collection
                await db.execute('''
                    INSERT INTO user_collections (user_id, card_id)
                    VALUES (?, ?)
                ''', (user_id, current_card_id))
                await db.commit()

                # Update user's balance
                await db.execute('''
                    UPDATE user_balances
                    SET balance = balance - ?
                    WHERE user_id = ?
                ''', (current_price, user_id))
                await db.commit()

            await interaction.response.send_message(f"You have successfully bought the card '{cards[current_index][1]}' for {current_price} coins.", ephemeral=True)

        previous_button = nextcord.ui.Button(label="<", style=nextcord.ButtonStyle.primary)
        previous_button.callback = previous_card

        next_button = nextcord.ui.Button(label=">", style=nextcord.ButtonStyle.primary)
        next_button.callback = next_card

        buy_button = nextcord.ui.Button(label="Buy", style=nextcord.ButtonStyle.success)
        buy_button.callback = buy_card

        view.add_item(previous_button)
        view.add_item(buy_button)
        view.add_item(next_button)

        # Send the first embed with the file attachment
        await interaction.followup.send(embed=embed, view=view, file=image_file)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")



MANAGER_ROLE_ID = 1157200601780859003
ASSISTANT_MANAGER_ROLE_ID = 1196199945242423467
SUSPENDED_ROLE_ID = 1229909875622940783

@client.slash_command(name="suspend", description="Suspend a user")
async def suspend(interaction: nextcord.Interaction,
                  user: nextcord.Member,
                  length: str,  # Length is now a text field
                  bail: int = None):
    # Check if the user has the required role
    if MANAGER_ROLE_ID in [role.id for role in interaction.user.roles] or \
       ASSISTANT_MANAGER_ROLE_ID in [role.id for role in interaction.user.roles]:

        # Add the suspended role to the user
        suspended_role = interaction.guild.get_role(SUSPENDED_ROLE_ID)
        await user.add_roles(suspended_role)

        # Create embed for suspension
        embed = nextcord.Embed(title="User Suspended", color=0xFF0000)
        embed.add_field(name="User", value=f"{user.mention}", inline=False)
        embed.add_field(name="Length", value=f"{length}", inline=True)

        if bail is not None:
            embed.add_field(name="Bail Amount", value=f"{bail} currency", inline=False)

        embed.set_footer(text=f"Suspended by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    else:
        # Create embed for no permission
        embed_error = nextcord.Embed(title="Permission Denied", color=0xFF0000)
        embed_error.add_field(name="Error", value="You don't have permission to run this command.", inline=False)
        embed_error.set_footer(text=f"Attempted by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed_error, ephemeral=True)
