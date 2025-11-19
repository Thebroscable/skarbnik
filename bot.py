import os
import discord
import asyncio

from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta

import emojis
import repository

# Wczytanie tokenu
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

async def wait_until(hour: int, minute: int):
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if target <= now:
        target += timedelta(days=1)

    await asyncio.sleep((target - now).total_seconds())

@tasks.loop(hours=24)
async def daily_debt_reminder():
    debts = repository.get_all_debts()

    for debtor_id, creditor_name, phone, amount, paid_amount, description in debts:
        try:
            user = await bot.fetch_user(int(debtor_id))
            await user.send(f"📢 **Przypomnienie:** Masz dług **{round(amount-paid_amount, 2)} zł** u {creditor_name}\n **Numer do przelewu:** {phone}\n **Opis:** {description}")
        except Exception as e:
            print(f"Nie udało się wysłać DM do {debtor_id}: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    repository.init_db()
    print(f'{bot.user} has initialized DB!')
    await bot.tree.sync()
    print(f"{bot.user} tree is ready!")

    await wait_until(18, 0)
    daily_debt_reminder.start()
    print("Scheduler started!")

# /add_debt <debtor> <amount> <description>
@bot.tree.command(name="add_debt", description="Dodaj dług dla użytkownika")
@app_commands.describe(
    debtor="Użytkownik który jest dłużnikiem",
    amount="Kwota długu",
    description="Opis długu"
)
async def add_debt(interaction: discord.Interaction, debtor: discord.Member, amount: float, description: str=""):
    creditor_id = str(interaction.user.id)
    debtor_id = str(debtor.id)

    if amount > 1000:
        await interaction.response.send_message(f"Chyba cie pojebało dziewczynko....")   

    repository.ensure_user_exists(debtor_id, debtor.display_name)
    repository.ensure_user_exists(creditor_id, interaction.user.display_name)

    rounded_amount = round(amount, 2)

    if description.strip() == "":
        description = "<brak opisu>"
    repository.add_debt(debtor_id, creditor_id, rounded_amount, description)

    await interaction.response.send_message(
        f"**Dodano dług:** {debtor.mention} jest winien {interaction.user.mention} **{rounded_amount} zł**. {emojis.emoji_CoTypierdolisz} \n**Opis:** {description}"
    )

# /register <numer>
@bot.tree.command(name="register", description="Zarejestruj numer telefonu do płatności")
@app_commands.describe(phone="Twój numer telefonu")
async def register(interaction: discord.Interaction, phone: str):
    user_id = str(interaction.user.id)
    username = str(interaction.user.display_name)  

    repository.register_user(user_id, username, phone)

    await interaction.response.send_message(
        f"{interaction.user.mention}, został zarejestrowany z numerem telefonu {phone} {emojis.emoji_haGay}"
    )

# /debt
@bot.tree.command(name="debt", description="Pokaż swoje długi")
async def debt(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    debts = repository.get_user_debts(user_id)

    if not debts:
        await interaction.response.send_message(f"Nie masz żadnych długów. {emojis.emoji_AaaKurwy}")
        return
    
    grouped = {}
    phone_numbers = {}
    for _, creditor_name, phone, amount, paid_amount, description in debts:
        grouped.setdefault(creditor_name, []).append((amount-paid_amount, description))
        phone_numbers[creditor_name] = phone
    
    msg = ""
    for creditor, debts_list in grouped.items():
        msg += f"**Długi u {creditor}:**\n"
        total = 0.0
        for amount, description in debts_list:
            msg += f"- {amount} zł | {description}\n"
            total = round(total + amount, 2)
        phone = phone_numbers.get(creditor)
        if phone:
            msg += f"**Suma: {total} zł | Telefon do przelewu: {phone}**\n\n"
        else:
            msg += f"**Suma: {total} zł | Numer telefonu nie został zarejestrowany**\n\n"

    await interaction.response.send_message(msg)

# /credit
@bot.tree.command(name="credit", description="Pokaż kto jest Ci winien pieniądze")
async def credit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    credit = repository.get_user_credit(user_id)

    if not credit:
        await interaction.response.send_message(f"Nikt nie jest Ci dłużny. {emojis.emoji_Alejaktobezwazeliny}")
        return

    grouped = {}
    for debtor_name, amount, paid_amount, description in credit:
        grouped.setdefault(debtor_name, []).append((amount-paid_amount, description))

    msg = ""
    for debtor, debts_list in grouped.items():
        msg += f"**Długi od {debtor}:**\n"
        total = 0.0
        for amount, description in debts_list:
            msg += f"- {amount} zł | {description}\n"
            total = round(total + amount, 2)
        msg += f"**Suma: {total} zł**\n\n"

    await interaction.response.send_message(msg)

# /split <amount> <description> <members>
@bot.tree.command(name="split", description="Podziel sumę między użytkowników")
@app_commands.describe(
    amount="Kwota do podziału",
    description="Opis długu",
    members="Użytkownicy, którzy mają zapłacić"
)
async def split(interaction: discord.Interaction, amount: float, description: str, members: str):
    """
    members: string z nickami użytkowników rozdzielonymi spacją lub przecinkiem
    """
    member_ids = []
    for member in interaction.guild.members:
        if str(member) in members or f"<@{member.id}>" in members:
            member_ids.append((str(member.id), member.display_name))
    
    if not member_ids:
        await interaction.response.send_message("Nie znaleziono żadnych użytkowników w liście.")
        return

    if description.strip() == "":
        description = "<brak opisu>"
    per_person = round(amount / len(member_ids), 2)

    creditor_id = str(interaction.user.id)
    repository.ensure_user_exists(creditor_id, interaction.user.display_name)

    for debtor_id, debtor_name in member_ids:
        repository.ensure_user_exists(debtor_id, debtor_name)
        repository.add_debt(debtor_id, creditor_id, per_person, description)

    debtors_list = ", ".join([f"<@{id}>" for id, _ in member_ids])
    await interaction.response.send_message(
        f"Podzielono kwotę **{amount} zł** *({per_person} zł na osobę)* między: {debtors_list}\n**Opis:** {description}"
    )

# /paid <creditor> <amount>
@bot.tree.command(name="paid", description="Użytkownik wysłał pieniądze")
@app_commands.describe(
    debtor="Użytkownik, który zapłacił",
    paid="Kwota wysłana przez użytkownika"
)
async def paid(interaction: discord.Interaction, debtor: discord.Member, paid: float):
    """
    Spłaca długi użytkownika debtor_id względem creditor_id.
    Spłaca od najstarszego długu.
    Zwraca komunikat tekstowy.
    """
    debts = repository.get_debts_between_users(interaction.user.id, debtor.id)

    if not debts:
        await interaction.response.send_message(
            f"{debtor.name} nie miał u ciebie żadnego długu... {emojis.emoji_skanerrage}"
        )
    else:
        remain = round(paid, 2)
        missing = 0

        for debt_id, amount, paid_amount in debts:
            left = round(amount - paid_amount, 2)

            if remain <= 0:
                missing = round(missing + left, 2)
                continue
            if remain >= left:
                repository.pay_debt(debt_id)
                remain = round(remain - left, 2)
            else:
                new_paid = round(paid_amount + remain, 2)
                remain = 0
                missing = round(left - remain, 2)
                repository.pay_debt_partial(debt_id, new_paid)


        if missing > 0:
            await interaction.response.send_message(
                f"Spłacono część długu {debtor.mention} względem {interaction.user.mention}. Brakuje jeszcze {missing:.2f} zł. {emojis.emoji_awryjniechcesz}"
            )
        elif remain > 0:
            await interaction.response.send_message(
                f"Wszystkie długi {debtor.mention} względem {interaction.user.mention} zostały spłacone. Nadpłata: **{remain:.2f} zł**. {emojis.emoji_AllahuAkbar}"
            )
        else:
            await interaction.response.send_message(
                f"Wszystkie długi {debtor.mention} względem {interaction.user.mention} zostały spłacone. {emojis.emoji_amen}"
            )
    
bot.run(TOKEN)