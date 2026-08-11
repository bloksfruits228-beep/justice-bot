import discord
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

class RoleTypeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="🌈 Градиент (2 цвета)", style=discord.ButtonStyle.primary, emoji="🌈")
    async def gradient_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.role_type = 'gradient'
        data.step = 1
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Вы выбрали **градиент**! Теперь введите **первый цвет** (HEX-код).\n📝 Напишите код в этот чат (сообщение увидите только вы).",
            embed=None, view=None
        )

    @discord.ui.button(label="🎨 Обычный цвет", style=discord.ButtonStyle.success, emoji="🎨")
    async def solid_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
            return
        data = user_data[self.user_id]
        data.role_type = 'solid'
        data.step = 1
        data.last_interaction = interaction
        await interaction.response.edit_message(
            content="✅ Вы выбрали **обычный цвет**! Введите **HEX-код** цвета.\n📝 Напишите код в этот чат (сообщение увидите только вы).",
            embed=None, view=None
        )

class IconChoiceView(discord.ui.View):
    def __init__(self, user_id, interaction):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.interaction = interaction

    @discord.ui.button(label="✅ Да, нужен значок", style=discord.ButtonStyle.success)
    async def yes_icon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша сессия!", ephemeral=True)
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
        super().__init__(timeout=300)
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

async def ask_role_type(interaction):
    embed = discord.Embed(
        title="🎨 Выберите тип роли",
        description="Какую роль вы хотите создать?\n\n🌈 **Градиент** — два цвета, плавный переход\n🎨 **Обычный цвет** — один цвет\n\nВыберите кнопку ниже:",
        color=0x2b2d31
    )
    view = RoleTypeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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

    if data.step == 1:
        hex_code = message.content.strip().replace('#', '').upper()
        if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
            await message.reply("❌ Неверный HEX-код! Нужно 6 символов (0-9, A-F). Попробуйте снова.", delete_after=10)
            await message.delete()
            return
        
        data.color1 = int(hex_code, 16)
        
        if data.role_type == 'gradient':
            data.step = 2
            await message.reply("✅ Первый цвет сохранён! Теперь напишите **второй цвет** (HEX-код).", delete_after=30)
        else:
            data.step = 3
            await message.reply("✅ Цвет сохранён! Сейчас спрошу про значок в ЛС.", delete_after=5)
            await asyncio.sleep(2)
            await ask_icon(message.author)
        
        await message.delete()
        return

    if data.step == 2:
        hex_code = message.content.strip().replace('#', '').upper()
        if len(hex_code) != 6 or not all(c in '0123456789ABCDEF' for c in hex_code):
            await message.reply("❌ Неверный HEX-код! Нужно 6 символов. Попробуйте снова.", delete_after=10)
            await message.delete()
            return
        data.color2 = int(hex_code, 16)
        data.step = 3
        await message.reply("✅ Второй цвет сохранён! Сейчас спрошу про значок в ЛС.", delete_after=5)
        await message.delete()
        await asyncio.sleep(2)
        await ask_icon(message.author)
        return

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
                    await message.delete()
                    return
                except Exception as e:
                    await message.reply(f"❌ Ошибка загрузки значка: {e}. Попробуйте снова.", delete_after=10)
                    await message.delete()
                    return
            else:
                await message.reply("❌ Это не изображение! Отправьте PNG/JPG/GIF.", delete_after=10)
                await message.delete()
                return
        else:
            await message.reply("❌ Пожалуйста, отправьте изображение в виде файла.", delete_after=10)
            await message.delete()
            return

    if data.step == 5:
        if len(message.content) > 100:
            await message.reply("❌ Слишком длинное название (макс. 100 символов).", delete_after=10)
            await message.delete()
            return
        data.role_name = message.content
        data.step = 6
        await message.reply("⏳ Создаю роль...", delete_after=5)
        await message.delete()
        await finish_role_creation(message.author)
        return

    await bot.process_commands(message)

async def ask_icon(user):
    embed = discord.Embed(
        title="🖼️ Нужен ли значок?",
        description="Нажмите **Да**, если хотите добавить значок к роли.\nНажмите **Нет**, чтобы пропустить этот шаг.",
        color=0x2b2d31
    )
    view = IconChoiceView(user.id, None)
    try:
        await user.send(embed=embed, view=view)
    except:
        await user.send("❌ Не могу отправить ЛС. Включите приём сообщений.")

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
        del user_data[user.id]

    except Exception as e:
        await user.send(f"❌ Ошибка: {e}")
        print(f"❌ Ошибка: {e}")

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
    try:
        synced = await bot.tree.sync()
        print(f"✅ Синхронизировано {len(synced)} команд")
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
