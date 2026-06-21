import pytest

from src.modules.auth.api.dependencies import get_current_user_id
from src.modules.auth.domain.models import CurrentUser


@pytest.mark.asyncio
async def test_current_user_id_keeps_numeric_id() -> None:
    user = CurrentUser(user_id="42", username="numeric")

    assert await get_current_user_id(user) == 42


@pytest.mark.asyncio
async def test_current_user_id_maps_string_ids_stably() -> None:
    first = CurrentUser(user_id="admin-1", username="admin")
    second = CurrentUser(user_id="user-1", username="user")

    first_id = await get_current_user_id(first)

    assert first_id == await get_current_user_id(first)
    assert first_id != await get_current_user_id(second)
    assert first_id > 0
