from fastapi import FastAPI

app = FastAPI(root_path="/api")

@app.get("/")
async def hello():
    return("message :hello from FastAPI + Gunicorn")



