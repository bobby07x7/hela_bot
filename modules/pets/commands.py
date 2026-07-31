from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.pets import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def adopt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/adopt <species> <name>"""
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage: /adopt <species> <name>\nSpecies: " + ", ".join(service.SPECIES)
        )
        return
    species = context.args[0].lower()
    name = " ".join(context.args[1:])
    tg_user = update.effective_user

    if species not in service.SPECIES:
        await update.effective_message.reply_text(
            await render("pets.invalid_species", species_list=", ".join(service.SPECIES))
        )
        return

    async with get_session() as session:
        existing = await service.get_pet(session, tg_user.id)
        if existing is not None:
            await update.effective_message.reply_text(
                await render("pets.already_have_pet", name=existing.name, species=existing.species)
            )
            return
        pet = await service.adopt_pet(session, tg_user.id, species, name)

    await update.effective_message.reply_text(await render("pets.adopt_success", species=species, name=pet.name))


@require_permission(PermissionLevel.USER)
async def pets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pets - show your current pet's status."""
    tg_user = update.effective_user
    async with get_session() as session:
        pet = await service.get_pet(session, tg_user.id)
        if pet is None:
            await update.effective_message.reply_text(await render("pets.no_pet"))
            return
        hunger = service.current_hunger(pet.hunger, pet.last_fed_at)
        text = await render(
            "pets.info", name=pet.name, species=pet.species, level=pet.level, xp=pet.xp,
            hunger=hunger, happiness=pet.happiness,
        )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def feed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        pet = await service.get_pet(session, tg_user.id)
        if pet is None:
            await update.effective_message.reply_text(await render("pets.no_pet"))
            return
        if service.is_already_full(pet.hunger, pet.last_fed_at):
            await update.effective_message.reply_text(await render("pets.feed_full", name=pet.name))
            return
        hunger, happiness = await service.feed_pet(session, pet)
        name = pet.name

    await update.effective_message.reply_text(await render("pets.feed_success", name=name, hunger=hunger, happiness=happiness))


@require_permission(PermissionLevel.USER)
async def releasepet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        pet = await service.get_pet(session, tg_user.id)
        if pet is None:
            await update.effective_message.reply_text(await render("pets.no_pet"))
            return
        name = pet.name
        await service.release_pet(session, pet)

    await update.effective_message.reply_text(await render("pets.release_success", name=name))
