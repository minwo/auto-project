from fastapi import APIRouter

from app.api import system, market, candidates, stocks, backtests

api_router = APIRouter()

api_router.include_router(system.router, prefix="/api")
api_router.include_router(market.router, prefix="/api")
api_router.include_router(candidates.router, prefix="/api")
api_router.include_router(stocks.router, prefix="/api")
api_router.include_router(backtests.router, prefix="/api")
