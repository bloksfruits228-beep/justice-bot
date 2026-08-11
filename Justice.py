import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import os
import sys
import io

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("❌ ОШИБКА: Не найден DISCORD_TOKEN в переменных окружения!")
    sys.exit(1)

TARGET_ROLE_ID = 1502637204487278744

OWNERS_FILE = "role_owners.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

role_owners = {}
if os.path.exists(OWNERS_FILE):
    try:
        with open(OWNERS_FILE, "r") as f:
            role_owners = json.load(f)
        print(f"✅ Загружено {len(role_owners)} записей о ролях")
    except:
        role_owners = {}

def save_owners():
    try:
        with open(OWNERS_FILE, "w") as f:
            json.dump(role_owners, f, indent=4)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")

user_data = {}

class RoleCreator:
    def __init__(self, user_id):
        self.user_id = user_id
        self.role_type = None
        self.color1 = None
        self.color2 = None
        self.icon_data = None  # Теперь храним байты изображения
        self.icon_filename = None
        self.role_name = None
        self.step = 0
        self.cancelled = False
        self.last_interaction = None
        self.created_at = asyncio.get_event_loop().time()
        self.temp_messages = []

    def add_temp_message(self, msg):
        self.temp_messages.append(msg)

    async def clear_temp_messages(self):
        for msg in self.temp_messages:
            try:
                await msg.delete()
            except:
                pass
        self.temp_messages = []

def is_owner_or_admin(interaction, role_id):
    user = interaction.user
    guild = interaction.guild
    
    if user == guild.owner:
        return True
    if user.guild_permissions.administrator:
        return True
    if str(role_id) in role_owners:
        return role_owners[str(role_id)] == str(user.id)
    return False

class CancelView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id

    @discord.ui.button(label="❌ Отменить создание", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id in user_data:
            data = user_data[interaction.user.id]
            await data.clear_temp_messages()
            del user_data[interaction.user.id]
        await interaction.response.edit_message(content="✅ Создание роли отменено.", embed=None, view=None)

class RoleTypeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id

    @discord.ui.button(label="🌈 Градиент (2 цвета)", style=discord.ButtonStyle.primary, emoji="🌈")
    async def gradient_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.role_type = 'gradient'
        data.step = 1
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Вы выбрали **градиент**! Теперь напишите **первый цвет** (HEX-код).\n📝 Напишите код в этот чат (сообщение увидите только вы).",
            embed=None, view=None
        )

    @discord.ui.button(label="🎨 Обычный цвет", style=discord.ButtonStyle.success, emoji="🎨")
    async def solid_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.role_type = 'solid'
        data.step = 1
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Вы выбрали **обычный цвет**! Теперь напишите **HEX-код** цвета.\n📝 Напишите код в этот чат (сообщение увидите только вы).",
            embed=None, view=None
        )

class IconChoiceView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id

    @discord.ui.button(label="✅ Да, нужен значок", style=discord.ButtonStyle.success)
    async def yes_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.step = 4
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="📸 Отправьте **одно изображение** (PNG/JPG/GIF) в этот чат.\n⚠️ Фото будет **автоматически удалено** после загрузки!\n\n📌 **Рекомендации:**\n• Изображение должно быть квадратным\n• Рекомендуемый размер: 128x128 или 256x256 пикселей\n• Поддерживаются форматы: PNG, JPG, GIF",
            embed=None, view=None
        )

    @discord.ui.button(label="❌ Нет, без значка", style=discord.ButtonStyle.secondary)
    async def no_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.icon_data = None
        data.step = 5
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Пропускаем значок. Теперь напишите **название роли** в этот чат (макс. 100 символов).",
            embed=None, view=None
        )

class ManageRoleView(discord.ui.View):
    def __init__(self, role_id, owner_id, user_id):
        super().__init__(timeout=600)
        self.role_id = role_id
        self.owner_id = owner_id
        self.user_id = user_id

    @discord.ui.button(label="✏️ Изменить роль", style=discord.ButtonStyle.primary)
    async def edit_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_admin(interaction, self.role_id):
            await interaction.response.send_message("❌ У вас нет прав изменять эту роль!", ephemeral=True)
            return
        await interaction.response.send_message("🔄 Начинаем изменение вашей роли...", ephemeral=True)
        await start_creation(interaction, edit_mode=True, old_role_id=self.role_id)

    @discord.ui.button(label="🗑️ Удалить роль", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_admin(interaction, self.role_id):
            await interaction.response.send_message("❌ У вас нет прав удалять эту роль!", ephemeral=True)
            return
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        if role:
            try:
                await role.delete()
                if str(self.role_id) in role_owners:
                    del role_owners[str(self.role_id)]
                    save_owners()
                await interaction.response.edit_message(content="✅ Роль успешно удалена!", view=None)
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Роль уже удалена.", ephemeral=True)

@bot.tree.command(name="создать_роль", description="Создает роль с градиентом или обычным цветом")
async def create_role(interaction: discord.Interaction):
    await start_creation(interaction, edit_mode=False)

@bot.tree.command(name="create_role", description="Create a role with gradient or solid color")
async def create_role_en(interaction: discord.Interaction):
    await start_creation_en(interaction, edit_mode=False)

@bot.tree.command(name="мои_роли", description="Показать все ваши кастомные роли")
async def my_roles(interaction: discord.Interaction):
    await show_my_roles(interaction)

@bot.tree.command(name="my_roles", description="Show all your custom roles")
async def my_roles_en(interaction: discord.Interaction):
    await show_my_roles(interaction)

@bot.tree.command(name="sync", description="[ADMIN] Синхронизировать команды")
@app_commands.default_permissions(administrator=True)
async def sync_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        command_list = "\n".join([f"`/{cmd.name}`" for cmd in synced])
        await interaction.followup.send(
            f"✅ Синхронизировано **{len(synced)}** команд!\n\nДоступные команды:\n{command_list}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

async def start_creation(interaction, edit_mode=False, old_role_id=None):
    user = interaction.user
    guild = interaction.guild

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

    if not edit_mode:
        for role in user.roles:
            if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
                view = ManageRoleView(role.id, user.id, user.id)
                embed = discord.Embed(
                    title="ℹ️ У вас уже есть кастомная роль!",
                    description=f"Ваша текущая роль: {role.mention}\n\nВы можете её **изменить** или **удалить**.\nИли нажмите 'Создать новую' — старая роль будет удалена.",
                    color=role.color
                )
                view.add_item(discord.ui.Button(
                    label="🆕 Создать новую (старая удалится)",
                    style=discord.ButtonStyle.success,
                    custom_id=f"force_new_{user.id}_{role.id}"
                ))
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

    user_data[user.id] = RoleCreator(user.id)
    await ask_role_type(interaction)

async def start_creation_en(interaction, edit_mode=False, old_role_id=None):
    user = interaction.user
    guild = interaction.guild

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

    if not edit_mode:
        for role in user.roles:
            if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
                view = ManageRoleView(role.id, user.id, user.id)
                embed = discord.Embed(
                    title="ℹ️ You already have a custom role!",
                    description=f"Your current role: {role.mention}\n\nYou can **edit** or **delete** it.\nOr click 'Create new' — old role will be deleted.",
                    color=role.color
                )
                view.add_item(discord.ui.Button(
                    label="🆕 Create new (old will be deleted)",
                    style=discord.ButtonStyle.success,
                    custom_id=f"force_new_{user.id}_{role.id}"
                ))
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

    user_data[user.id] = RoleCreator(user.id)
    await ask_role_type_en(interaction)

async def ask_role_type(interaction):
    embed = discord.Embed(
        title="🎨 Выберите тип роли",
        description="Какую роль вы хотите создать?\n\n🌈 **Градиент** — два цвета, плавный переход\n🎨 **Обычный цвет** — один цвет\n\nВыберите кнопку ниже:",
        color=0x2b2d31
    )
    view = RoleTypeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def ask_role_type_en(interaction):
    embed = discord.Embed(
        title="🎨 Choose role type",
        description="What role do you want to create?\n\n🌈 **Gradient** — two colors, smooth transition\n🎨 **Solid color** — one color\n\nChoose a button below:",
        color=0x2b2d31
    )
    view = RoleTypeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def show_my_roles(interaction):
    user = interaction.user
    guild = interaction.guild
    
    my_roles = []
    for role in user.roles:
        if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
            my_roles.append(role)
    
    if not my_roles:
        embed = discord.Embed(
            title="📋 Ваши роли",
            description="У вас нет кастомных ролей, созданных через бота.\nИспользуйте `/создать_роль` или `/create_role` чтобы создать новую!",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 Ваши кастомные роли",
        description="Нажмите на роль, чтобы управлять ей:",
        color=0x2b2d31
    )
    
    view = discord.ui.View(timeout=120)
    
    for role in my_roles:
        view.add_item(discord.ui.Button(
            label=role.name[:80],
            style=discord.ButtonStyle.primary,
            custom_id=f"manage_role_{role.id}",
            emoji="⚙️"
        ))
    
    view.add_item(discord.ui.Button(
        label="🔄 Обновить",
        style=discord.ButtonStyle.secondary,
        custom_id="refresh_roles"
    ))
    view.add_item(discord.ui.Button(
        label="❌ Закрыть",
        style=discord.ButtonStyle.danger,
        custom_id="close_roles"
    ))
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def safe_delete_message(message):
    if message.guild:
        try:
            await message.delete()
        except:
            pass

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

    try:
        if data.step == 1:
            hex_code = message.content.strip().replace('#', '').upper()
            if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
                await message.reply(
                    "❌ Неверный HEX-код! Нужно 6 символов (0-9, A-F).\n"
                    "📌 **Где найти HEX-код?**\n"
                    "• Сайт: https://htmlcolorcodes.com\n"
                    "• Выберите цвет → скопируйте код после #\n"
                    "• Пример: #FF5733 → напишите `FF5733`\n"
                    "• Или используйте пипетку в фотошопе/GIMP\n\n"
                    "🔄 Попробуйте снова:",
                    delete_after=20
                )
                await safe_delete_message(message)
                return
            
            data.color1 = int(hex_code, 16)
            
            if data.role_type == 'gradient':
                data.step = 2
                await message.reply("✅ Первый цвет сохранён! Теперь напишите **второй цвет** (HEX-код).", delete_after=30)
            else:
                data.step = 3
                await message.reply("✅ Цвет сохранён! Теперь выберите, нужен ли значок.", delete_after=5)
                await asyncio.sleep(1)
                await ask_icon_in_channel(message.channel, message.author)
            
            await safe_delete_message(message)
            return

        if data.step == 2:
            hex_code = message.content.strip().replace('#', '').upper()
            if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
                await message.reply(
                    "❌ Неверный HEX-код! Нужно 6 символов (0-9, A-F).\n"
                    "📌 Пример: #FF5733 → напишите `FF5733`\n"
                    "🔄 Попробуйте снова:",
                    delete_after=15
                )
                await safe_delete_message(message)
                return
            data.color2 = int(hex_code, 16)
            data.step = 3
            await message.reply("✅ Второй цвет сохранён! Теперь выберите, нужен ли значок.", delete_after=5)
            await safe_delete_message(message)
            await asyncio.sleep(1)
            await ask_icon_in_channel(message.channel, message.author)
            return

        if data.step == 4:
            if not message.guild:
                await message.reply("❌ Пожалуйста, отправьте фото в канал сервера, а не в ЛС.", delete_after=10)
                await safe_delete_message(message)
                return
            
            if message.attachments:
                attachment = message.attachments[0]
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    try:
                        img_data = await attachment.read()
                        data.icon_data = img_data
                        data.icon_filename = attachment.filename
                        data.step = 5
                        await message.reply("✅ Изображение загружено! Теперь напишите **название роли** (макс. 100 символов).", delete_after=30)
                        await safe_delete_message(message)
                        return
                    except Exception as e:
                        await message.reply(f"❌ Ошибка загрузки изображения: {e}. Попробуйте снова.", delete_after=10)
                        await safe_delete_message(message)
                        return
                else:
                    await message.reply("❌ Это не изображение! Отправьте PNG/JPG/GIF.", delete_after=10)
                    await safe_delete_message(message)
                    return
            else:
                await message.reply("❌ Пожалуйста, отправьте изображение в виде файла.", delete_after=10)
                await safe_delete_message(message)
                return

        if data.step == 5:
            if len(message.content) > 100:
                await message.reply("❌ Слишком длинное название (макс. 100 символов).", delete_after=10)
                await safe_delete_message(message)
                return
            data.role_name = message.content
            data.step = 6
            await message.reply("⏳ Создаю роль...", delete_after=5)
            await safe_delete_message(message)
            await finish_role_creation(message.author)
            return
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}. Начните заново с /создать_роль", delete_after=10)
        if message.author.id in user_data:
            del user_data[message.author.id]
        await safe_delete_message(message)

    await bot.process_commands(message)

async def ask_icon_in_channel(channel, user):
    embed = discord.Embed(
        title="🖼️ Нужен ли значок для роли?",
        description="Нажмите **Да**, если хотите добавить значок к роли.\nНажмите **Нет**, чтобы пропустить этот шаг.\n\n📌 Изображение будет загружено **напрямую как иконка роли**, без создания эмодзи.",
        color=0x2b2d31
    )
    view = IconChoiceView(user.id)
    await channel.send(f"{user.mention}, выберите действие:", embed=embed, view=view)

async def finish_role_creation(user):
    data = user_data[user.id]
    guild = user.guild

    try:
        target_role = guild.get_role(TARGET_ROLE_ID)
        target_position = target_role.position if target_role else 0

        # Подготавливаем иконку для роли (если есть)
        icon_bytes = data.icon_data if data.icon_data else None
        icon_file = None
        if icon_bytes:
            icon_file = discord.File(io.BytesIO(icon_bytes), filename="role_icon.png")

        if data.role_type == 'gradient':
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
            
            # Устанавливаем иконку для первой роли (если есть)
            if icon_bytes and icon_file:
                try:
                    await role1.edit(display_icon=icon_file)
                except Exception as e:
                    print(f"⚠️ Не удалось установить иконку: {e}")
            
            if target_role:
                await role1.edit(position=target_position + 1)
                await role2.edit(position=target_position + 2)
            
            role_owners[str(role1.id)] = str(user.id)
            role_owners[str(role2.id)] = str(user.id)
            await user.add_roles(role1, role2)
            
            embed = discord.Embed(
                title="✅ Градиентная роль создана!",
                description=f"**Название:** {data.role_name}\n**Цвета:** #{hex(data.color1)[2:].upper()} и #{hex(data.color2)[2:].upper()}\n**Значок:** {'✅ Загружен' if icon_bytes else 'Нет'}\n\nРоли: {role1.mention}, {role2.mention}",
                color=data.color1
            )
            view = ManageRoleView(role1.id, user.id, user.id)
            
        else:
            role = await guild.create_role(
                name=data.role_name,
                colour=discord.Colour(data.color1),
                reason=f"Создана пользователем {user}"
            )
            
            # Устанавливаем иконку (если есть)
            if icon_bytes and icon_file:
                try:
                    await role.edit(display_icon=icon_file)
                except Exception as e:
                    print(f"⚠️ Не удалось установить иконку: {e}")
            
            if target_role:
                await role.edit(position=target_position + 1)
            
            role_owners[str(role.id)] = str(user.id)
            await user.add_roles(role)
            
            embed = discord.Embed(
                title="✅ Обычная роль создана!",
                description=f"**Название:** {data.role_name}\n**Цвет:** #{hex(data.color1)[2:].upper()}\n**Значок:** {'✅ Загружен' if icon_bytes else 'Нет'}\n\nРоль: {role.mention}",
                color=data.color1
            )
            view = ManageRoleView(role.id, user.id, user.id)

        save_owners()
        await user.send(embed=embed, view=view)
        await data.clear_temp_messages()
        if user.id in user_data:
            del user_data[user.id]

    except Exception as e:
        await user.send(f"❌ Ошибка: {e}")
        print(f"❌ Ошибка: {e}")
        if user.id in user_data:
            await user_data[user.id].clear_temp_messages()
            del user_data[user.id]

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
            return
        
        if custom_id.startswith("manage_role_"):
            role_id = int(custom_id.split("_")[2])
            role = interaction.guild.get_role(role_id)
            if role:
                view = ManageRoleView(role.id, interaction.user.id, interaction.user.id)
                embed = discord.Embed(
                    title=f"⚙️ Управление ролью: {role.name}",
                    description="Выберите действие:",
                    color=role.color
                )
                await interaction.response.edit_message(embed=embed, view=view)
            return
        
        if custom_id == "refresh_roles":
            await show_my_roles(interaction)
            return
        
        if custom_id == "close_roles":
            await interaction.response.edit_message(content="📋 Список закрыт.", view=None)
            return

@bot.tree.command(name="удалить_чужую_роль", description="[ADMIN] Удалить роль другого пользователя")
@app_commands.default_permissions(administrator=True)
async def admin_delete_role(interaction: discord.Interaction, role: discord.Role):
    if not (interaction.user == interaction.guild.owner or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ Только владелец или администратор!", ephemeral=True)
        return
    
    if str(role.id) in role_owners:
        try:
            await role.delete()
            del role_owners[str(role.id)]
            save_owners()
            await interaction.response.send_message(f"✅ Роль {role.name} удалена!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Эта роль не создана ботом.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} запущен!')
    print(f'📊 Загружено ролей: {len(role_owners)}')
    print(f'🎯 Целевая роль ID: {TARGET_ROLE_ID}')
    
    for guild in bot.guilds:
        bot_member = guild.get_member(bot.user.id)
        if bot_member:
            permissions = bot_member.guild_permissions
            print(f"\n📋 Сервер: {guild.name}")
            print(f"   👑 Администратор: {permissions.administrator}")
            print(f"   ⚙️ Управление ролями: {permissions.manage_roles}")
            print(f"   📝 Управление выражениями: {permissions.manage_emojis_and_stickers}")
            print(f"   💬 Отправка сообщений: {permissions.send_messages}")
            print(f"   📖 Чтение истории: {permissions.read_message_history}")
            
            if not permissions.administrator:
                print("   ⚠️ Бот НЕ является администратором! Некоторые функции могут не работать.")
    
    try:
        synced = await bot.tree.sync()
        print(f"\n✅ Синхронизировано {len(synced)} команд")
        print("📝 Доступные команды:")
        for cmd in synced:
            print(f"   /{cmd.name} - {cmd.description}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ОШИБКА: Токен не найден!")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import os
import sys

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("❌ ОШИБКА: Не найден DISCORD_TOKEN в переменных окружения!")
    sys.exit(1)

TARGET_ROLE_ID = 1502637204487278744

OWNERS_FILE = "role_owners.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

role_owners = {}
if os.path.exists(OWNERS_FILE):
    try:
        with open(OWNERS_FILE, "r") as f:
            role_owners = json.load(f)
        print(f"✅ Загружено {len(role_owners)} записей о ролях")
    except:
        role_owners = {}

def save_owners():
    try:
        with open(OWNERS_FILE, "w") as f:
            json.dump(role_owners, f, indent=4)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")

user_data = {}

class RoleCreator:
    def __init__(self, user_id):
        self.user_id = user_id
        self.role_type = None
        self.color1 = None
        self.color2 = None
        self.icon = None
        self.icon_loaded = False
        self.role_name = None
        self.step = 0
        self.cancelled = False
        self.last_interaction = None
        self.created_at = asyncio.get_event_loop().time()
        self.temp_messages = []

    def add_temp_message(self, msg):
        self.temp_messages.append(msg)

    async def clear_temp_messages(self):
        for msg in self.temp_messages:
            try:
                await msg.delete()
            except:
                pass
        self.temp_messages = []

def is_owner_or_admin(interaction, role_id):
    user = interaction.user
    guild = interaction.guild
    
    if user == guild.owner:
        return True
    if user.guild_permissions.administrator:
        return True
    if str(role_id) in role_owners:
        return role_owners[str(role_id)] == str(user.id)
    return False

class CancelView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id

    @discord.ui.button(label="❌ Отменить создание", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id in user_data:
            data = user_data[interaction.user.id]
            await data.clear_temp_messages()
            del user_data[interaction.user.id]
        await interaction.response.edit_message(content="✅ Создание роли отменено.", embed=None, view=None)

class RoleTypeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id

    @discord.ui.button(label="🌈 Градиент (2 цвета)", style=discord.ButtonStyle.primary, emoji="🌈")
    async def gradient_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.role_type = 'gradient'
        data.step = 1
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Вы выбрали **градиент**! Теперь напишите **первый цвет** (HEX-код).\n📝 Напишите код в этот чат (сообщение увидите только вы).",
            embed=None, view=None
        )

    @discord.ui.button(label="🎨 Обычный цвет", style=discord.ButtonStyle.success, emoji="🎨")
    async def solid_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.role_type = 'solid'
        data.step = 1
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Вы выбрали **обычный цвет**! Теперь напишите **HEX-код** цвета.\n📝 Напишите код в этот чат (сообщение увидите только вы).",
            embed=None, view=None
        )

class IconChoiceView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id

    @discord.ui.button(label="✅ Да, нужен значок", style=discord.ButtonStyle.success)
    async def yes_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.step = 4
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="📸 Отправьте **одно изображение** (PNG/JPG/GIF) в этот чат.\n⚠️ Фото будет **автоматически удалено** после загрузки!",
            embed=None, view=None
        )

    @discord.ui.button(label="❌ Нет, без значка", style=discord.ButtonStyle.secondary)
    async def no_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        if interaction.user.id not in user_data:
            await interaction.response.send_message("❌ Сессия истекла. Начните заново с /создать_роль", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.icon = None
        data.step = 5
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Пропускаем значок. Теперь напишите **название роли** в этот чат (макс. 100 символов).",
            embed=None, view=None
        )

class ManageRoleView(discord.ui.View):
    def __init__(self, role_id, owner_id, user_id):
        super().__init__(timeout=600)
        self.role_id = role_id
        self.owner_id = owner_id
        self.user_id = user_id

    @discord.ui.button(label="✏️ Изменить роль", style=discord.ButtonStyle.primary)
    async def edit_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_admin(interaction, self.role_id):
            await interaction.response.send_message("❌ У вас нет прав изменять эту роль!", ephemeral=True)
            return
        await interaction.response.send_message("🔄 Начинаем изменение вашей роли...", ephemeral=True)
        await start_creation(interaction, edit_mode=True, old_role_id=self.role_id)

    @discord.ui.button(label="🗑️ Удалить роль", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_admin(interaction, self.role_id):
            await interaction.response.send_message("❌ У вас нет прав удалять эту роль!", ephemeral=True)
            return
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        if role:
            try:
                await role.delete()
                if str(self.role_id) in role_owners:
                    del role_owners[str(self.role_id)]
                    save_owners()
                await interaction.response.edit_message(content="✅ Роль успешно удалена!", view=None)
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Роль уже удалена.", ephemeral=True)

@bot.tree.command(name="создать_роль", description="Создает роль с градиентом или обычным цветом")
async def create_role(interaction: discord.Interaction):
    await start_creation(interaction, edit_mode=False)

@bot.tree.command(name="create_role", description="Create a role with gradient or solid color")
async def create_role_en(interaction: discord.Interaction):
    await start_creation_en(interaction, edit_mode=False)

@bot.tree.command(name="мои_роли", description="Показать все ваши кастомные роли")
async def my_roles(interaction: discord.Interaction):
    await show_my_roles(interaction)

@bot.tree.command(name="my_roles", description="Show all your custom roles")
async def my_roles_en(interaction: discord.Interaction):
    await show_my_roles(interaction)

@bot.tree.command(name="sync", description="[ADMIN] Синхронизировать команды")
@app_commands.default_permissions(administrator=True)
async def sync_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        command_list = "\n".join([f"`/{cmd.name}`" for cmd in synced])
        await interaction.followup.send(
            f"✅ Синхронизировано **{len(synced)}** команд!\n\nДоступные команды:\n{command_list}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

async def start_creation(interaction, edit_mode=False, old_role_id=None):
    user = interaction.user
    guild = interaction.guild

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

    if not edit_mode:
        for role in user.roles:
            if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
                view = ManageRoleView(role.id, user.id, user.id)
                embed = discord.Embed(
                    title="ℹ️ У вас уже есть кастомная роль!",
                    description=f"Ваша текущая роль: {role.mention}\n\nВы можете её **изменить** или **удалить**.\nИли нажмите 'Создать новую' — старая роль будет удалена.",
                    color=role.color
                )
                view.add_item(discord.ui.Button(
                    label="🆕 Создать новую (старая удалится)",
                    style=discord.ButtonStyle.success,
                    custom_id=f"force_new_{user.id}_{role.id}"
                ))
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

    user_data[user.id] = RoleCreator(user.id)
    await ask_role_type(interaction)

async def start_creation_en(interaction, edit_mode=False, old_role_id=None):
    user = interaction.user
    guild = interaction.guild

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

    if not edit_mode:
        for role in user.roles:
            if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
                view = ManageRoleView(role.id, user.id, user.id)
                embed = discord.Embed(
                    title="ℹ️ You already have a custom role!",
                    description=f"Your current role: {role.mention}\n\nYou can **edit** or **delete** it.\nOr click 'Create new' — old role will be deleted.",
                    color=role.color
                )
                view.add_item(discord.ui.Button(
                    label="🆕 Create new (old will be deleted)",
                    style=discord.ButtonStyle.success,
                    custom_id=f"force_new_{user.id}_{role.id}"
                ))
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

    user_data[user.id] = RoleCreator(user.id)
    await ask_role_type_en(interaction)

async def ask_role_type(interaction):
    embed = discord.Embed(
        title="🎨 Выберите тип роли",
        description="Какую роль вы хотите создать?\n\n🌈 **Градиент** — два цвета, плавный переход\n🎨 **Обычный цвет** — один цвет\n\nВыберите кнопку ниже:",
        color=0x2b2d31
    )
    view = RoleTypeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def ask_role_type_en(interaction):
    embed = discord.Embed(
        title="🎨 Choose role type",
        description="What role do you want to create?\n\n🌈 **Gradient** — two colors, smooth transition\n🎨 **Solid color** — one color\n\nChoose a button below:",
        color=0x2b2d31
    )
    view = RoleTypeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def show_my_roles(interaction):
    user = interaction.user
    guild = interaction.guild
    
    my_roles = []
    for role in user.roles:
        if str(role.id) in role_owners and role_owners[str(role.id)] == str(user.id):
            my_roles.append(role)
    
    if not my_roles:
        embed = discord.Embed(
            title="📋 Ваши роли",
            description="У вас нет кастомных ролей, созданных через бота.\nИспользуйте `/создать_роль` или `/create_role` чтобы создать новую!",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 Ваши кастомные роли",
        description="Нажмите на роль, чтобы управлять ей:",
        color=0x2b2d31
    )
    
    view = discord.ui.View(timeout=120)
    
    for role in my_roles:
        view.add_item(discord.ui.Button(
            label=role.name[:80],
            style=discord.ButtonStyle.primary,
            custom_id=f"manage_role_{role.id}",
            emoji="⚙️"
        ))
    
    view.add_item(discord.ui.Button(
        label="🔄 Обновить",
        style=discord.ButtonStyle.secondary,
        custom_id="refresh_roles"
    ))
    view.add_item(discord.ui.Button(
        label="❌ Закрыть",
        style=discord.ButtonStyle.danger,
        custom_id="close_roles"
    ))
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def safe_delete_message(message):
    if message.guild:
        try:
            await message.delete()
        except:
            pass

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

    try:
        if data.step == 1:
            hex_code = message.content.strip().replace('#', '').upper()
            if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
                await message.reply(
                    "❌ Неверный HEX-код! Нужно 6 символов (0-9, A-F).\n"
                    "📌 **Где найти HEX-код?**\n"
                    "• Сайт: https://htmlcolorcodes.com\n"
                    "• Выберите цвет → скопируйте код после #\n"
                    "• Пример: #FF5733 → напишите `FF5733`\n"
                    "• Или используйте пипетку в фотошопе/GIMP\n\n"
                    "🔄 Попробуйте снова:",
                    delete_after=20
                )
                await safe_delete_message(message)
                return
            
            data.color1 = int(hex_code, 16)
            
            if data.role_type == 'gradient':
                data.step = 2
                await message.reply("✅ Первый цвет сохранён! Теперь напишите **второй цвет** (HEX-код).", delete_after=30)
            else:
                data.step = 3
                await message.reply("✅ Цвет сохранён! Теперь выберите, нужен ли значок.", delete_after=5)
                await asyncio.sleep(1)
                await ask_icon_in_channel(message.channel, message.author)
            
            await safe_delete_message(message)
            return

        if data.step == 2:
            hex_code = message.content.strip().replace('#', '').upper()
            if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
                await message.reply(
                    "❌ Неверный HEX-код! Нужно 6 символов (0-9, A-F).\n"
                    "📌 Пример: #FF5733 → напишите `FF5733`\n"
                    "🔄 Попробуйте снова:",
                    delete_after=15
                )
                await safe_delete_message(message)
                return
            data.color2 = int(hex_code, 16)
            data.step = 3
            await message.reply("✅ Второй цвет сохранён! Теперь выберите, нужен ли значок.", delete_after=5)
            await safe_delete_message(message)
            await asyncio.sleep(1)
            await ask_icon_in_channel(message.channel, message.author)
            return

        if data.step == 4:
            if not message.guild:
                await message.reply("❌ Пожалуйста, отправьте фото в канал сервера, а не в ЛС.", delete_after=10)
                await safe_delete_message(message)
                return
            
            if message.attachments:
                attachment = message.attachments[0]
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    try:
                        img_data = await attachment.read()
                        emoji_name = f"r{data.user_id}"
                        if len(emoji_name) < 2:
                            emoji_name = f"r{data.user_id}"
                        if len(emoji_name) > 32:
                            emoji_name = emoji_name[:32]
                        emoji = await message.guild.create_custom_emoji(name=emoji_name, image=img_data)
                        data.icon = str(emoji)
                        data.step = 5
                        await message.reply("✅ Значок добавлен! Теперь напишите **название роли** (макс. 100 символов).", delete_after=30)
                        await safe_delete_message(message)
                        return
                    except Exception as e:
                        await message.reply(f"❌ Ошибка загрузки значка: {e}. Попробуйте снова.", delete_after=10)
                        await safe_delete_message(message)
                        return
                else:
                    await message.reply("❌ Это не изображение! Отправьте PNG/JPG/GIF.", delete_after=10)
                    await safe_delete_message(message)
                    return
            else:
                await message.reply("❌ Пожалуйста, отправьте изображение в виде файла.", delete_after=10)
                await safe_delete_message(message)
                return

        if data.step == 5:
            if len(message.content) > 100:
                await message.reply("❌ Слишком длинное название (макс. 100 символов).", delete_after=10)
                await safe_delete_message(message)
                return
            data.role_name = message.content
            data.step = 6
            await message.reply("⏳ Создаю роль...", delete_after=5)
            await safe_delete_message(message)
            await finish_role_creation(message.author)
            return
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}. Начните заново с /создать_роль", delete_after=10)
        if message.author.id in user_data:
            del user_data[message.author.id]
        await safe_delete_message(message)

    await bot.process_commands(message)

async def ask_icon_in_channel(channel, user):
    embed = discord.Embed(
        title="🖼️ Нужен ли значок?",
        description="Нажмите **Да**, если хотите добавить значок к роли.\nНажмите **Нет**, чтобы пропустить этот шаг.",
        color=0x2b2d31
    )
    view = IconChoiceView(user.id)
    await channel.send(f"{user.mention}, выберите действие:", embed=embed, view=view)

async def finish_role_creation(user):
    data = user_data[user.id]
    guild = user.guild

    try:
        target_role = guild.get_role(TARGET_ROLE_ID)
        target_position = target_role.position if target_role else 0

        if data.role_type == 'gradient':
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
            
            if data.icon:
                try:
                    await role1.edit(name=f"{data.icon} {data.role_name}")
                    await role2.edit(name=f"{data.icon} ◀ {data.role_name}")
                except:
                    pass
            
            if target_role:
                await role1.edit(position=target_position + 1)
                await role2.edit(position=target_position + 2)
            
            role_owners[str(role1.id)] = str(user.id)
            role_owners[str(role2.id)] = str(user.id)
            await user.add_roles(role1, role2)
            
            embed = discord.Embed(
                title="✅ Градиентная роль создана!",
                description=f"**Название:** {data.role_name}\n**Цвета:** #{hex(data.color1)[2:].upper()} и #{hex(data.color2)[2:].upper()}\n**Значок:** {data.icon if data.icon else 'Нет'}\n\nРоли: {role1.mention}, {role2.mention}",
                color=data.color1
            )
            view = ManageRoleView(role1.id, user.id, user.id)
            
        else:
            role = await guild.create_role(
                name=data.role_name,
                colour=discord.Colour(data.color1),
                reason=f"Создана пользователем {user}"
            )
            
            if data.icon:
                try:
                    await role.edit(name=f"{data.icon} {data.role_name}")
                except:
                    pass
            
            if target_role:
                await role.edit(position=target_position + 1)
            
            role_owners[str(role.id)] = str(user.id)
            await user.add_roles(role)
            
            embed = discord.Embed(
                title="✅ Обычная роль создана!",
                description=f"**Название:** {data.role_name}\n**Цвет:** #{hex(data.color1)[2:].upper()}\n**Значок:** {data.icon if data.icon else 'Нет'}\n\nРоль: {role.mention}",
                color=data.color1
            )
            view = ManageRoleView(role.id, user.id, user.id)

        save_owners()
        await user.send(embed=embed, view=view)
        await data.clear_temp_messages()
        if user.id in user_data:
            del user_data[user.id]

    except Exception as e:
        await user.send(f"❌ Ошибка: {e}")
        print(f"❌ Ошибка: {e}")
        if user.id in user_data:
            await user_data[user.id].clear_temp_messages()
            del user_data[user.id]

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
            return
        
        if custom_id.startswith("manage_role_"):
            role_id = int(custom_id.split("_")[2])
            role = interaction.guild.get_role(role_id)
            if role:
                view = ManageRoleView(role.id, interaction.user.id, interaction.user.id)
                embed = discord.Embed(
                    title=f"⚙️ Управление ролью: {role.name}",
                    description="Выберите действие:",
                    color=role.color
                )
                await interaction.response.edit_message(embed=embed, view=view)
            return
        
        if custom_id == "refresh_roles":
            await show_my_roles(interaction)
            return
        
        if custom_id == "close_roles":
            await interaction.response.edit_message(content="📋 Список закрыт.", view=None)
            return

@bot.tree.command(name="удалить_чужую_роль", description="[ADMIN] Удалить роль другого пользователя")
@app_commands.default_permissions(administrator=True)
async def admin_delete_role(interaction: discord.Interaction, role: discord.Role):
    if not (interaction.user == interaction.guild.owner or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ Только владелец или администратор!", ephemeral=True)
        return
    
    if str(role.id) in role_owners:
        try:
            await role.delete()
            del role_owners[str(role.id)]
            save_owners()
            await interaction.response.send_message(f"✅ Роль {role.name} удалена!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Эта роль не создана ботом.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} запущен!')
    print(f'📊 Загружено ролей: {len(role_owners)}')
    print(f'🎯 Целевая роль ID: {TARGET_ROLE_ID}')
    
    for guild in bot.guilds:
        bot_member = guild.get_member(bot.user.id)
        if bot_member:
            permissions = bot_member.guild_permissions
            print(f"\n📋 Сервер: {guild.name}")
            print(f"   👑 Администратор: {permissions.administrator}")
            print(f"   ⚙️ Управление ролями: {permissions.manage_roles}")
            print(f"   📝 Управление выражениями: {permissions.manage_emojis_and_stickers}")
            print(f"   💬 Отправка сообщений: {permissions.send_messages}")
            print(f"   📖 Чтение истории: {permissions.read_message_history}")
            
            if not permissions.administrator:
                print("   ⚠️ Бот НЕ является администратором! Некоторые функции могут не работать.")
    
    try:
        synced = await bot.tree.sync()
        print(f"\n✅ Синхронизировано {len(synced)} команд")
        print("📝 Доступные команды:")
        for cmd in synced:
            print(f"   /{cmd.name} - {cmd.description}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ОШИБКА: Токен не найден!")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
