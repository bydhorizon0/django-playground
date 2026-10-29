from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router

api = NinjaAPI(
    title="Community API",
    version="1.0",
    description="Community API",
)

api.add_router("/auth", accounts_router)
