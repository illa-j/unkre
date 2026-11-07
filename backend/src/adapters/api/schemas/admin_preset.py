from adapters.api.schemas.common import Page
from adapters.api.schemas.preset import CreatePresetRequest, PresetResponse


class AdminCreatePresetRequest(CreatePresetRequest):
    is_public: bool = True


AdminPresetPage = Page[PresetResponse]
