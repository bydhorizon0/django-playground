from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.posts.api import router as posts_router

api = NinjaAPI(
    title="Community API",
    version="1.0",
    description="Community API",
)

api.add_router("/auth", accounts_router)
api.add_router("/", posts_router)
