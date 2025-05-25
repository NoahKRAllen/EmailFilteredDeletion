from fastapi import FastAPI


app = FastAPI()

@app.get("/get-message ")

def hello(name: str):
    return {'Message': "Congrats" + name + '! This is your first API'}
