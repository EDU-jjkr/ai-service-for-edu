# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routers import deck, activity, lesson_plan, doubt_solver, textbook

app = FastAPI(
    title="Educational Platform AI Service",
    description="AI-powered content generation and doubt solving",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(deck.router, prefix="/api", tags=["Deck Generation"])
app.include_router(activity.router, prefix="/api", tags=["Activity Generation"])
app.include_router(lesson_plan.router, prefix="/api", tags=["Lesson Plans"])
app.include_router(doubt_solver.router, prefix="/api", tags=["Doubt Solver"])
app.include_router(textbook.router, prefix="/api", tags=["Textbook Index"])

@app.get("/")
async def root():
    return {
        "message": "Educational Platform AI Service",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
