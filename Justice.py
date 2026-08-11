import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Файл для хранения владельцев ролей (чтобы после перезапуска бота данные не терялись)
OWNERS_FILE = "role_owners.json"

# Загружаем данные о владельцах
if os.path.exists(OWNERS_FILE):
    with open(OWNERS_FILE, "r") as f:
        role_owners = json.load(f)
else:
    role_owners = {}

def save_owners():
    with open(OWNERS_FILE, "w") as f:
        json.dump(role_owners, f, indent=4)

# Временные данные для создания роли
user_data = {}

class RoleCreator:
    def __init__(self, user_id):
        self.user_id = user_id
        self.color1 = None
        self.color2 = None
        self.icon = None
        self.icon_loaded = False
        self.role_name = None
        self.step = 0  # 0 - цвет1, 1 - цвет2, 2 - иконка?, 3 - название, 4 - финиш
        self.cancelled = False
        self.message_to_delete = None  # для удаления сообщений с цветами

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} запущен!')
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(e)

# =============== КНОПКА ОТМЕНЫ ===============
class CancelView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="❌ Отменить создание", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id in user_data:
            del user_data[interaction.user.id]
        await interaction.response.edit_message(content="✅ Создание роли отменено.", embed=None, view=None)

# =============== ВЫБОР ЗНАЧКА ===============
class IconChoiceView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="✅ Да, нужен значок", style=discord.ButtonStyle.success)
    async def yes_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.step = 4  # ждем фото
        await interaction.response.edit_message(
            content="📸 Отправьте **одно изображение** (PNG/JPG/GIF) в этот чат. Оно станет значком роли.",
            embed=None, view=None
        )

    @discord.ui.button(label="❌ Нет, без значка", style=discord.ButtonStyle.secondary)
    async def no_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.icon = None
        data.step = 5  # переходим к названию
        await interaction.response.edit_message(
            content="✅ Пропускаем значок. Теперь напишите **название роли** в этот чат (макс. 100 символов).",
            embed=None, view=None
        )

# =============== КНОПКИ ДЛЯ УПРАВЛЕНИЯ РОЛЬЮ ===============
class ManageRoleView(discord.ui.View):
    def __init__(self, role_id, owner_id):
        super().__init__(timeout=60)
        self.role_id = role_id
        self.owner_id = owner_id

    @discord.ui.button(label="✏️ Изменить роль", style=discord.ButtonStyle.primary)
    async def edit_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Это не ваша роль! Вы не можете её изменять.", ephemeral=True)
            return
        # Запускаем процесс изменения
        await interaction.response.send_message("🔄 Начинаем изменение вашей роли...", ephemeral=True)
        # Можно запустить тот же цикл создания, но с обновлением
        await start_creation(interaction, edit_mode=True, old_role_id=self.role_id)

    @discord.ui.button(label="🗑️ Удалить роль", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Это не ваша роль! Вы не можете её удалять.", ephemeral=True)
            return
        
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        if role:
            try:
                await role.delete()
                # Удаляем из базы
                if str(self.role_id) in role_owners:
                    del role_owners[str(self.role_id)]
                    save_owners()
                await interaction.response.edit_message(content="✅ Роль успешно удалена!", view=None)
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка при удалении: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Роль уже удалена или не найдена.", ephemeral=True)

# =============== ГЛАВНАЯ КОМАНДА ===============
@bot.tree.command(name="создать_роль", description="Создает роль с градиентом из двух цветов")
async def create_role(interaction: discord.Interaction):
    await start_creation(interaction, edit_mode=False)

async def start_creation(interaction, edit_mode=False, old_role_id=None):
    user = interaction.user
    guild = interaction.guild

    # Проверяем, есть ли у пользователя уже роль (если не в режиме редактирования)
    if not edit_mode:
        for role in user.roles:
            if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
                # У пользователя уже есть кастомная роль
                view = ManageRoleView(role.id, user.id)
                embed = discord.Embed(
                    title="ℹ️ У вас уже есть кастомная роль!",
                    description=f"Ваша текущая роль: {role.mention}\n\n"
                                f"Вы можете её **изменить** или **удалить**, используя кнопки ниже.\n"
                                f"Или нажмите 'Создать новую' — тогда старая роль будет удалена.",
                    color=role.color
                )
                view.add_item(discord.ui.Button(
                    label="🆕 Создать новую (старая удалится)",
                    style=discord.ButtonStyle.success,
                    custom_id=f"force_new_{user.id}_{role.id}"
                ))
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

    # Если режим редактирования — удаляем старую роль
    if edit_mode and old_role_id:
        old_role = guild.get_role(old_role_id)
        if old_role:
            try:
                await old_role.delete()
                if str(old_role_id) in role_owners:
                    del role_owners[str(old_role_id)]
                    save_owners()
            except:
                pass

    # Создаем новую сессию
    user_data[user.id] = RoleCreator(user.id)
    await ask_color1(interaction)

# =============== ЗАПРОС ПЕРВОГО ЦВЕТА ===============
async def ask_color1(interaction):
    embed = discord.Embed(
        title="🎨 Шаг 1 из 4: Первый цвет",
        description="Напишите **HEX-код** первого цвета (6 символов).\n"
                    "Пример: `FF5733` или `#FF5733` (решётку можно не ставить).\n\n"
                    "📌 **Как получить HEX-код?**\n"
                    "Зайдите на сайт **htmlcolorcodes.com**, выберите цвет и скопируйте код после `#`.\n"
                    "Или используйте пипетку в любом графическом редакторе.\n\n"
                    "🟢 Напишите код в чат (в течение 5 минут).",
        color=0x2b2d31
    )
    view = CancelView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# =============== ОБРАБОТЧИК СООБЩЕНИЙ ===============
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith('/'):
        await bot.process_commands(message)
        return

    user_id = message.author.id
    if user_id not in user_data:
        await bot.process_commands(message)
        return

    data = user_data[user_id]
    if data.cancelled:
        return

    # ===== ШАГ 1: ПЕРВЫЙ ЦВЕТ =====
    if data.step == 0:
        hex_code = message.content.strip().replace('#', '').upper()
        if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
            await message.reply("❌ Неверный HEX-код! Нужно 6 символов (0-9, A-F). Попробуйте снова.", delete_after=10)
            return
        data.color1 = int(hex_code, 16)
        data.step = 1
        await message.reply("✅ Первый цвет сохранён! Теперь напишите **второй цвет** (HEX-код).", delete_after=30)
        try:
            await message.delete()
        except:
            pass
        return

    # ===== ШАГ 2: ВТОРОЙ ЦВЕТ =====
    if data.step == 1:
        hex_code = message.content.strip().replace('#', '').upper()
        if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
            await message.reply("❌ Неверный HEX-код! Нужно 6 символов. Попробуйте снова.", delete_after=10)
            return
        data.color2 = int(hex_code, 16)
        data.step = 2
        await message.reply("✅ Второй цвет сохранён! Сейчас спрошу про значок...", delete_after=5)
        try:
            await message.delete()
        except:
            pass
        # Отправляем кнопки для выбора значка
        await ask_icon(message.author)
        return

    # ===== ШАГ 4: ПРИЕМ ФОТО ДЛЯ ЗНАЧКА =====
    if data.step == 4:
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith('image/'):
                try:
                    img_data = await attachment.read()
                    emoji_name = f"role_{data.user_id}_{message.guild.id}"
                    emoji = await message.guild.create_custom_emoji(name=emoji_name, image=img_data)
                    data.icon = str(emoji)
                    data.step = 5
                    await message.reply("✅ Значок добавлен! Теперь напишите **название роли** (макс. 100 символов).", delete_after=30)
                    try:
                        await message.delete()
                    except:
                        pass
                    return
                except Exception as e:
                    await message.reply(f"❌ Ошибка загрузки значка: {e}. Попробуйте снова или нажмите Отмена.")
                    return
            else:
                await message.reply("❌ Это не изображение! Отправьте файл PNG/JPG/GIF.")
                return
        else:
            await message.reply("❌ Пожалуйста, отправьте изображение в виде файла (вложения).")
            return

    # ===== ШАГ 5: ПРИЕМ НАЗВАНИЯ =====
    if data.step == 5:
        if len(message.content) > 100:
            await message.reply("❌ Слишком длинное название (макс. 100 символов).", delete_after=10)
            return
        data.role_name = message.content
        data.step = 6
        await message.reply("⏳ Создаю роль...", delete_after=5)
        try:
            await message.delete()
        except:
            pass
        # ФИНАЛ: создаем роль
        await finish_role_creation(message.author)
        return

    await bot.process_commands(message)

# =============== ЗАПРОС ЗНАЧКА ===============
async def ask_icon(user):
    embed = discord.Embed(
        title="🖼️ Шаг 2 из 4: Нужен ли значок?",
        description="Нажмите **Да**, если хотите добавить значок к роли (потребуется загрузить фото).\n"
                    "Нажмите **Нет**, чтобы пропустить этот шаг.",
        color=0x2b2d31
    )
    view = IconChoiceView(user.id)
    try:
        await user.send(embed=embed, view=view)
        await user.send("📩 Я отправил вам кнопки в личные сообщения (проверьте ЛС)!")
    except:
        await user.send("❌ Не могу отправить вам ЛС. Включите приём сообщений от участников сервера.")

# =============== СОЗДАНИЕ РОЛИ ===============
async def finish_role_creation(user):
    data = user_data[user.id]
    guild = user.guild

    try:
        # Создаем две роли (для визуального градиента)
        role1 = await guild.create_role(
            name=f"{data.role_name}",
            colour=discord.Colour(data.color1),
            reason=f"Создана пользователем {user}"
        )
        role2 = await guild.create_role(
            name=f"◀ {data.role_name}",
            colour=discord.Colour(data.color2),
            reason=f"Создана пользователем {user}"
        )

        # Если есть значок - добавляем его в название
        if data.icon:
            try:
                await role1.edit(name=f"{data.icon} {data.role_name}")
                await role2.edit(name=f"{data.icon} ◀ {data.role_name}")
            except:
                pass

        # Сохраняем владельца для ОБЕИХ ролей
        role_owners[str(role1.id)] = str(user.id)
        role_owners[str(role2.id)] = str(user.id)
        save_owners()

        # Выдаем роли пользователю
        await user.add_roles(role1, role2)

        # Кнопки управления
        view = ManageRoleView(role1.id, user.id)

        embed = discord.Embed(
            title="✅ Роль создана!",
            description=f"**Название:** {data.role_name}\n"
                        f"**Цвета:** #{hex(data.color1)[2:].upper()} и #{hex(data.color2)[2:].upper()}\n"
                        f"**Значок:** {data.icon if data.icon else 'Нет'}\n\n"
                        f"Роли выданы вам: {role1.mention}, {role2.mention}\n\n"
                        f"🔽 Используйте кнопки ниже, чтобы управлять своей ролью.",
            color=data.color1
        )
        await user.send(embed=embed, view=view)

        # Удаляем данные пользователя
        del user_data[user.id]

    except Exception as e:
        await user.send(f"❌ Ошибка: {e}")

# =============== ОБРАБОТКА НАЖАТИЯ НА КНОПКУ "СОЗДАТЬ НОВУЮ" ===============
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("force_new_"):
            parts = custom_id.split("_")
            user_id = int(parts[2])
            old_role_id = int(parts[3])
            
            if interaction.user.id != user_id:
                await interaction.response.send_message("❌ Это не ваша кнопка!", ephemeral=True)
                return
            
            # Удаляем старую роль
            old_role = interaction.guild.get_role(old_role_id)
            if old_role:
                try:
                    await old_role.delete()
                    if str(old_role_id) in role_owners:
                        del role_owners[str(old_role_id)]
                        save_owners()
                except:
                    pass
            
            await interaction.response.edit_message(content="🔄 Создаём новую роль...", view=None)
            await start_creation(interaction, edit_mode=False)

# =============== ЗАПУСК БОТА ===============
bot.run('ВАШ_ТОКЕН_БОТА')
