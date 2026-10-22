from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Backend Guichet Citoyen IA - Asnieres"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/test")
def test():
    return {
        "message": "Communication frontend/backend fonctionnelle"
    }