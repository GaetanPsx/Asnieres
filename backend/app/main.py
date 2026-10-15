from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Backend Guichet Citoyen IA - Asnieres"}


@app.get("/health")
def health():
    return {"status": "ok"}