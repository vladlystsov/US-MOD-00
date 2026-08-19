from fastapi import FastAPI
from src.database import Base, engine
from src.exceptions import register_exception_handlers
from src.api import blocking_reasons, events, moderation, tickets

app = FastAPI(title="NeoMarket Moderation Service")

Base.metadata.create_all(bind=engine)

register_exception_handlers(app)

app.include_router(events.router)
app.include_router(events.b2b_router)
app.include_router(moderation.router)
app.include_router(tickets.router)
app.include_router(blocking_reasons.router)


@app.get("/")
def root():
    return {"message": "Moderation Service"}
