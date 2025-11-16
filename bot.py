import os

import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

import utils
import repository

# Wczytanie tokenu
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    repository.init_db()
    print(f'{bot.user} has initialized DB!')
    await bot.tree.sync()
    print(f"{bot.user} is ready!")

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

    repository.ensure_user_exists(debtor_id, debtor.display_name)
    repository.ensure_user_exists(creditor_id, interaction.user.display_name)

    rounded_amount = round(amount, 2)

    if description.strip() == "":
        description = "<brak opisu>"
    repository.add_debt(debtor_id, creditor_id, rounded_amount, description)

    await interaction.response.send_message(
        f"**Dodano dług:** {debtor.mention} jest ci winien {rounded_amount} zł. {utils.emoji_CoTypierdolisz} \n**Opis:** {description}"
    )

# /register <numer>
@bot.tree.command(name="register", description="Zarejestruj numer telefonu do płatności")
@app_commands.describe(phone="Twój numer telefonu")
async def register(interaction: discord.Interaction, phone: str):
    user_id = str(interaction.user.id)
    username = str(interaction.user.display_name)  

    repository.register_user(user_id, username, phone)

    await interaction.response.send_message(
        f"{interaction.user.mention}, został zarejestrowany z numerem telefonu {phone} {utils.emoji_haGay}"
    )

# /debt
@bot.tree.command(name="debt", description="Pokaż swoje długi")
async def debt(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    debts = repository.get_user_debts(user_id)

    if not debts:
        await interaction.response.send_message(f"Nie masz żadnych długów. {utils.emoji_AaaKurwy}")
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
        await interaction.response.send_message(f"Nikt nie jest Ci dłużny. {utils.emoji_Alejaktobezwazeliny}")
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

# /pay <creditor> <amount>
@bot.tree.command(name="pay", description="Spłać dług u użytkownika")
@app_commands.describe(
    creditor="Użytkownik, któremu trzeba zapłacić",
    paid="Kwota wysłana do użytkownika"
)
async def pay(interaction: discord.Interaction, creditor: discord.Member, paid: float):
    """
    Spłaca długi użytkownika debtor_id względem creditor_id.
    Spłaca od najstarszego długu.
    Zwraca komunikat tekstowy.
    """
    debts = repository.get_user_debts_for_creditor(interaction.user.id, creditor.id)

    if not debts:
        await interaction.response.send_message(
            f"Nie masz żadnych nieopłaconych długów względem tej osoby. Nie gadaj, że i tak przelałeś kase? Ale frajer... {utils.emoji_skanerrage}"
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
                f"Spłacono część długu. Brakuje jeszcze {missing:.2f} zł. {utils.emoji_awryjniechcesz}"
            )
        elif remain > 0:
            await interaction.response.send_message(
                f"Wszystkie długi u {creditor.mention} zostały spłacone. Nadpłata: **{remain:.2f} zł**. {utils.emoji_AllahuAkbar}"
            )
        else:
            await interaction.response.send_message(
                f"Wszystkie długi u {creditor.mention} zostały spłacone. {utils.emoji_amen}"
            )
    
bot.run(TOKEN)