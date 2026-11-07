from uuid import UUID

from sqlalchemy import case, delete, func, insert, or_, select

from adapters.database.models import (
    GenerationPresetModel,
    preset_favorites,
    preset_saves,
)
from adapters.database.repositiries import CrudRepository
from domain.entities.preset import GenerationPreset
from ports import DatabaseManagerInterface


class PresetRepository(CrudRepository[GenerationPresetModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, GenerationPresetModel)

    async def _like_stats(
        self, preset_id: UUID, user_id: UUID | None = None
    ) -> tuple[int, bool]:
        count = await self._db.scalar(
            select(func.count())
            .select_from(preset_favorites)
            .where(preset_favorites.c.preset_id == preset_id)
        )
        favorite = False
        if user_id is not None:
            favorite = (
                await self._db.scalar(
                    select(func.count())
                    .select_from(preset_favorites)
                    .where(
                        preset_favorites.c.preset_id == preset_id,
                        preset_favorites.c.user_id == user_id,
                    )
                )
            ) > 0
        return int(count or 0), bool(favorite)

    async def _is_saved(self, preset_id: UUID, user_id: UUID | None = None) -> bool:
        if user_id is None:
            return False
        return bool(
            await self._db.scalar(
                select(func.count())
                .select_from(preset_saves)
                .where(
                    preset_saves.c.preset_id == preset_id,
                    preset_saves.c.user_id == user_id,
                )
            )
        )

    async def _stats(
        self, preset_id: UUID, user_id: UUID | None = None
    ) -> tuple[int, bool, bool]:
        count, favorite = await self._like_stats(preset_id, user_id)
        return count, favorite, await self._is_saved(preset_id, user_id)

    async def create_preset(self, preset: GenerationPreset) -> GenerationPreset:
        row = await self.create(GenerationPresetModel.from_entity(preset))
        return row.to_entity()

    async def get_for_user(
        self, user_id: UUID, preset_id: UUID
    ) -> GenerationPreset | None:
        row = await self._db.scalar(
            select(GenerationPresetModel).where(
                GenerationPresetModel.id == preset_id,
                GenerationPresetModel.user_id == user_id,
            )
        )
        if row is None:
            return None
        count, favorite, saved = await self._stats(preset_id, user_id)
        return row.to_entity(
            favorites_count=count, is_favorite=favorite, is_saved=saved
        )

    async def get_accessible(
        self, user_id: UUID, preset_id: UUID
    ) -> GenerationPreset | None:
        row = await self._db.scalar(
            select(GenerationPresetModel).where(
                GenerationPresetModel.id == preset_id,
                or_(
                    GenerationPresetModel.user_id == user_id,
                    GenerationPresetModel.is_public.is_(True),
                ),
            )
        )
        if row is None:
            return None
        count, favorite, saved = await self._stats(preset_id, user_id)
        return row.to_entity(
            favorites_count=count, is_favorite=favorite, is_saved=saved
        )

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[GenerationPreset]:
        counts = (
            select(func.count())
            .select_from(preset_favorites)
            .where(preset_favorites.c.preset_id == GenerationPresetModel.id)
            .correlate(GenerationPresetModel)
            .scalar_subquery()
        )
        liked = (
            select(func.count())
            .select_from(preset_favorites)
            .where(
                preset_favorites.c.preset_id == GenerationPresetModel.id,
                preset_favorites.c.user_id == user_id,
            )
            .correlate(GenerationPresetModel)
            .scalar_subquery()
        )
        saved = (
            select(func.count())
            .select_from(preset_saves)
            .where(
                preset_saves.c.preset_id == GenerationPresetModel.id,
                preset_saves.c.user_id == user_id,
            )
            .correlate(GenerationPresetModel)
            .scalar_subquery()
        )
        rows = (
            await self._db.execute(
                select(
                    GenerationPresetModel,
                    counts.label("favorites_count"),
                    liked.label("is_favorite"),
                    saved.label("is_saved"),
                )
                .where(
                    or_(
                        GenerationPresetModel.user_id == user_id,
                        GenerationPresetModel.is_public.is_(True),
                    )
                )
                .order_by(
                    case((GenerationPresetModel.user_id == user_id, 0), else_=1),
                    GenerationPresetModel.created_at.desc(),
                    GenerationPresetModel.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [
            row[0].to_entity(
                favorites_count=int(row[1] or 0),
                is_favorite=bool(row[2]),
                is_saved=bool(row[3]),
            )
            for row in rows
        ]

    async def update_for_user(
        self, user_id: UUID, preset_id: UUID, values: dict[str, object]
    ) -> GenerationPreset | None:
        row = await self.get_for_user(user_id, preset_id)
        if row is None:
            return None
        updated = await self.update(preset_id, values)
        if updated is None:
            return None
        count, favorite, saved = await self._stats(preset_id, user_id)
        return updated.to_entity(
            favorites_count=count, is_favorite=favorite, is_saved=saved
        )

    async def delete_for_user(self, user_id: UUID, preset_id: UUID) -> bool:
        removed = await self._db.scalar(
            delete(GenerationPresetModel)
            .where(
                GenerationPresetModel.id == preset_id,
                GenerationPresetModel.user_id == user_id,
            )
            .returning(GenerationPresetModel.id)
            .execution_options(synchronize_session=False)
        )
        return removed is not None

    async def get_any(self, preset_id: UUID) -> GenerationPreset | None:
        row = await self._db.get(GenerationPresetModel, preset_id)
        if row is None:
            return None
        count, _ = await self._like_stats(preset_id)
        return row.to_entity(favorites_count=count)

    async def update_any(
        self, preset_id: UUID, values: dict[str, object]
    ) -> GenerationPreset | None:
        updated = await self.update(preset_id, values)
        if updated is None:
            return None
        count, _ = await self._like_stats(preset_id)
        return updated.to_entity(favorites_count=count)

    async def delete_any(self, preset_id: UUID) -> bool:
        return await self.delete(preset_id)

    async def list_any(
        self, *, query: str | None, limit: int, offset: int
    ) -> tuple[list[GenerationPreset], int]:
        counts = (
            select(func.count())
            .select_from(preset_favorites)
            .where(preset_favorites.c.preset_id == GenerationPresetModel.id)
            .correlate(GenerationPresetModel)
            .scalar_subquery()
        )
        statement = select(
            GenerationPresetModel, counts.label("favorites_count")
        ).order_by(
            GenerationPresetModel.created_at.desc(),
            GenerationPresetModel.id.desc(),
        )
        total_statement = select(func.count(GenerationPresetModel.id))
        if query:
            needle = f"%{query.strip().lower()}%"
            condition = func.lower(GenerationPresetModel.name).like(needle) | func.lower(
                GenerationPresetModel.prompt
            ).like(needle)
            statement = statement.where(condition)
            total_statement = total_statement.where(condition)
        rows = (
            await self._db.execute(statement.limit(limit).offset(offset))
        ).all()
        total = int(await self._db.scalar(total_statement) or 0)
        return [
            row[0].to_entity(favorites_count=int(row[1] or 0)) for row in rows
        ], total

    async def favorite(self, user_id: UUID, preset_id: UUID) -> int:
        exists = await self._db.scalar(
            select(preset_favorites.c.user_id).where(
                preset_favorites.c.user_id == user_id,
                preset_favorites.c.preset_id == preset_id,
            )
        )
        if exists is None:
            await self._db.execute(
                insert(preset_favorites).values(
                    user_id=user_id, preset_id=preset_id
                )
            )
        count, _ = await self._like_stats(preset_id)
        return count

    async def unfavorite(self, user_id: UUID, preset_id: UUID) -> int:
        await self._db.execute(
            delete(preset_favorites).where(
                preset_favorites.c.user_id == user_id,
                preset_favorites.c.preset_id == preset_id,
            )
        )
        count, _ = await self._like_stats(preset_id)
        return count

    async def save(self, user_id: UUID, preset_id: UUID) -> bool:
        exists = await self._db.scalar(
            select(preset_saves.c.user_id).where(
                preset_saves.c.user_id == user_id,
                preset_saves.c.preset_id == preset_id,
            )
        )
        if exists is None:
            await self._db.execute(
                insert(preset_saves).values(user_id=user_id, preset_id=preset_id)
            )
        return True

    async def unsave(self, user_id: UUID, preset_id: UUID) -> bool:
        await self._db.execute(
            delete(preset_saves).where(
                preset_saves.c.user_id == user_id,
                preset_saves.c.preset_id == preset_id,
            )
        )
        return False
