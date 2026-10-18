from fastapi import FastAPI

app = FastAPI(title = "DICOM Image Manager")

@app.get("/health")
def health():
    return {"status": "ok"}
