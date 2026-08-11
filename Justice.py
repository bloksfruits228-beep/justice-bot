async def finish_role_creation(user):
    data = user_data[user.id]
    guild = user.guild

    try:
        target_role = guild.get_role(TARGET_ROLE_ID)
        target_position = target_role.position if target_role else 0

        icon_bytes = data.icon_data if data.icon_data else None
        icon_file = None
        if icon_bytes:
            icon_file = discord.File(io.BytesIO(icon_bytes), filename="role_icon.png")

        if data.role_type == 'gradient':
            print(f"🌈 СОЗДАЮ ГРАДИЕНТ: {data.role_name}")
            print(f"   Цвет 1: #{hex(data.color1)[2:].upper()}")
            print(f"   Цвет 2: #{hex(data.color2)[2:].upper()}")
            
            # Создаём первую роль с первым цветом
            role1 = await guild.create_role(
                name=f"◀ {data.role_name}",
                colour=discord.Colour(data.color1),
                reason=f"Создана пользователем {user}"
            )
            print(f"   ✅ Роль 1 создана: {role1.name} (ID: {role1.id})")
            
            # Создаём вторую роль со вторым цветом
            role2 = await guild.create_role(
                name=f"{data.role_name}",
                colour=discord.Colour(data.color2),
                reason=f"Создана пользователем {user}"
            )
            print(f"   ✅ Роль 2 создана: {role2.name} (ID: {role2.id})")
            
            # Устанавливаем иконку на ПЕРВУЮ роль (она будет выше)
            if icon_bytes and icon_file:
                try:
                    await role1.edit(display_icon=icon_file)
                    print(f"   ✅ Иконка установлена на роль 1")
                except Exception as e:
                    print(f"   ⚠️ Не удалось установить иконку: {e}")
            
            # Позиционируем роли ВЫШЕ целевой роли
            if target_role:
                await role1.edit(position=target_position + 1)
                await role2.edit(position=target_position + 2)
                print(f"   ✅ Роли позиционированы выше {target_role.name} (поз. {target_position})")
            
            # Сохраняем владельца для ОБЕИХ ролей
            role_owners[str(role1.id)] = str(user.id)
            role_owners[str(role2.id)] = str(user.id)
            
            # Выдаём ОБЕ роли пользователю
            await user.add_roles(role1, role2)
            print(f"   ✅ Роли выданы пользователю {user.name}")
            
            embed = discord.Embed(
                title="✅ Градиентная роль создана!",
                description=f"**Название:** {data.role_name}\n"
                            f"**Цвета:** #{hex(data.color1)[2:].upper()} и #{hex(data.color2)[2:].upper()}\n"
                            f"**Значок:** {'✅ Загружен' if icon_bytes else '❌ Нет'}\n\n"
                            f"Роли выданы:\n{role1.mention}\n{role2.mention}\n\n"
                            f"📌 Роли находятся **выше** роли {target_role.mention if target_role else '(не найдена)'}",
                color=data.color1
            )
            view = ManageRoleView(role1.id, user.id, user.id)
            
        else:
            print(f"🎨 СОЗДАЮ ОБЫЧНУЮ РОЛЬ: {data.role_name}")
            print(f"   Цвет: #{hex(data.color1)[2:].upper()}")
            
            role = await guild.create_role(
                name=data.role_name,
                colour=discord.Colour(data.color1),
                reason=f"Создана пользователем {user}"
            )
            print(f"   ✅ Роль создана: {role.name} (ID: {role.id})")
            
            if icon_bytes and icon_file:
                try:
                    await role.edit(display_icon=icon_file)
                    print(f"   ✅ Иконка установлена")
                except Exception as e:
                    print(f"   ⚠️ Не удалось установить иконку: {e}")
            
            if target_role:
                await role.edit(position=target_position + 1)
                print(f"   ✅ Роль позиционирована выше {target_role.name}")
            
            role_owners[str(role.id)] = str(user.id)
            await user.add_roles(role)
            print(f"   ✅ Роль выдана пользователю {user.name}")
            
            embed = discord.Embed(
                title="✅ Обычная роль создана!",
                description=f"**Название:** {data.role_name}\n"
                            f"**Цвет:** #{hex(data.color1)[2:].upper()}\n"
                            f"**Значок:** {'✅ Загружен' if icon_bytes else '❌ Нет'}\n\n"
                            f"Роль: {role.mention}\n"
                            f"📌 Роль находится **выше** роли {target_role.mention if target_role else '(не найдена)'}",
                color=data.color1
            )
            view = ManageRoleView(role.id, user.id, user.id)

        save_owners()
        await user.send(embed=embed, view=view)
        await data.clear_temp_messages()
        if user.id in user_data:
            del user_data[user.id]
            
        print(f"🎉 ГОТОВО! Роль создана для {user.name}")

    except Exception as e:
        await user.send(f"❌ Ошибка: {e}")
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        if user.id in user_data:
            await user_data[user.id].clear_temp_messages()
            del user_data[user.id]
