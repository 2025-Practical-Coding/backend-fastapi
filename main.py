import json
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from dotenv import load_dotenv
from game_state import GameState, Character, Region
from chat_interaction import chatWithCharacter, ending, getOpening, sayGoodBye

# ========== API 서버 ==========
load_dotenv()
app = FastAPI(title="RPG Chat Game API")
GS = GameState.loadFromFile("Data.json", "extract_relationship.json")
GS.initialize()

class ChatRequest(BaseModel):
    slug: str
    name: str
    userInput: str

@app.get("/state")
def getState():
    current = GS.currentCharacter
    if not current:
        raise HTTPException(status_code=404, detail="No character selected")
    return {
        "region": GS.getRegionName(current.slug),
        "currentCharacter": {
            "slug": current.slug,
            "name": current.name,
            "subtitle": current.subtitle,
            "affinity": current.affinity,
            "convCount": GS.convCounts.get(current.slug, 0)
        },
        "totalRemaining": GS.maxRounds - GS.currentRound,
        "maxAffinity": GS.affinityThreshold,
        "convLimit": GS.convLimit,
    }

@app.get("/opening")
def getOpeningRoute():
    if not GS.currentCharacter:
        raise HTTPException(status_code=404, detail="No character selected")
    print(f"[DEBUG] Current Character: {GS.currentCharacter.name}, Region: {getattr(GS.currentCharacter, 'region', None)}")
    return {
        "opening": getOpening(GS, GS.currentCharacter),
        "currentCharacter": GS.currentCharacter
    }

@app.post("/chat")
def postChat(req: ChatRequest = Body(...)):
    if not GS.currentCharacter:
        raise HTTPException(status_code=404, detail="Game over")
    if req.slug != GS.currentCharacter.slug:
        raise HTTPException(status_code=400, detail="This is not the character you're talking to.")

    try:
        print(f"[INFO] /chat called - slug: {req.slug}, input: {req.userInput}")
        response = chatWithCharacter(GS, req.slug, req.name, req.userInput)
    except Exception as e:
        print("[ERROR] chatWithCharacter failed:", e)
        raise HTTPException(status_code=500, detail=str(e))

    if GS.isConversationDone(req.slug):
        goodbye = sayGoodBye(GS, GS.currentCharacter)
        GS.selectNextCharacter()
        
        # 단순히 gameOver 여부만 응답
        return {
            "responses": [response, goodbye],
            "gameOver": GS.isGameOver()
        }

    # 일반 대화일 경우 gameOver=False 포함
    return {
        "response": response,
        "gameOver": False
    }

@app.get("/result")
def getResult():
    if not GS.isGameOver():
        raise HTTPException(status_code=400, detail="Game is not over yet.")
    return ending(GS)