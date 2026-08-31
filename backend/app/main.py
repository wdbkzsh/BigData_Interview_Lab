from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.attempts import router as attempts_router
from app.api.daily_tasks import router as daily_tasks_router
from app.api.knowledge import router as knowledge_router
from app.api.questions import router as questions_router
from app.api.reviews import router as reviews_router
from app.api.wrong_book import router as wrong_book_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST", "PUT"],
)

app.include_router(attempts_router)
app.include_router(daily_tasks_router)
app.include_router(knowledge_router)
app.include_router(questions_router)
app.include_router(reviews_router)
app.include_router(wrong_book_router)


@app.get("/health")
def health():
    return {"status": "ok"}