from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.api.bootstrap import ensure_bootstrap_admin
from adapters.api.guard import configure_guard
from adapters.api.middlewares import authentication_middleware
from adapters.api.rate_limit import RouteRateLimitMiddleware
from adapters.api.routes.admin import router as admin_router
from adapters.api.routes.admin_catalog import router as admin_catalog_router
from adapters.api.routes.admin_panel import router as admin_panel_router
from adapters.api.routes.admin_preset import router as admin_preset_router
from adapters.api.routes.admin_settings import router as admin_settings_router
from adapters.api.routes.admin_workflow import router as admin_workflow_router
from adapters.api.routes.generation import router as generation_router
from adapters.api.routes.health import router as health_router
from adapters.api.routes.lora import router as lora_router
from adapters.api.routes.payment import router as payment_router
from adapters.api.routes.preset import router as preset_router
from adapters.api.routes.promo import router as promo_router
from adapters.api.routes.referral import router as referral_router
from adapters.api.routes.user import router as user_router
from adapters.api.routes.workflow import router as workflow_router
from adapters.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_bootstrap_admin(get_settings())
    yield


app = FastAPI(lifespan=lifespan)
app.middleware("http")(authentication_middleware)
configure_guard(app, get_settings())
app.add_middleware(RouteRateLimitMiddleware, settings=get_settings())
app.include_router(health_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(admin_settings_router)
app.include_router(admin_panel_router)
app.include_router(admin_workflow_router)
app.include_router(admin_catalog_router)
app.include_router(admin_preset_router)
app.include_router(payment_router)
app.include_router(referral_router)
app.include_router(preset_router)
app.include_router(promo_router)
app.include_router(generation_router)
app.include_router(workflow_router)
app.include_router(lora_router)
