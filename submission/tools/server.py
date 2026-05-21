import os
import sys
import yaml
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Ensure submission path is in Python path for local modular references
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.schema import StateStore, QuestState, QuestStep, CompanyState
from agents.foundry_agents import MasterNarrator, StrategistAgent, DesignerAgent, MarketerAgent
from tools.code_interpreter_wrappers import validate_positioning, validate_landing_page, validate_marketing_email

app = FastAPI(
    title="Your Company Is the Dungeon - Server",
    description="Backend API for local and visual reasoning runs."
)

# Enable CORS for local cross-origin development if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent file-based store
STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "state.json")
store = StateStore(filepath=STATE_FILE)

class PitchRequest(BaseModel):
    pitch: str
    company_name: Optional[str] = "Acolyte's Venture"

@app.get("/api/state")
def get_state():
    """Gets the current company state from disk."""
    state = store.load()
    if not state:
        # Return a clean empty-like structure or indicator
        return {"initialized": False, "state": None}
    return {"initialized": True, "state": state.model_dump()}

@app.post("/api/init")
def initialize_game(payload: PitchRequest):
    """Initializes the game session with a custom pitch and decomposes it."""
    pitch = payload.pitch
    company_name = payload.company_name or "My Spawned Venture"
    
    # 1. Initialize State Store
    state = store.initialize_new_company(
        name=company_name,
        pitch=pitch,
        description="A startup forged in QuestForge."
    )
    store.log_event("SESSION_START", "system", f"Initialized fresh startup session for company: {company_name}")
    
    # 2. Master Narrator Decomposes the Pitch into 3 Quests
    narrator = MasterNarrator()
    try:
        steps_data = narrator.decompose_pitch(pitch)
    except Exception as e:
        # Fallback to offline mock steps if any SDK issue occurs
        steps_data = [
            {
                "id": "step_1_positioning",
                "title": "Define Your Target Audience and Positioning",
                "description": f"Use the Strategist to scope target clients and shape the positioning of: '{pitch}'",
                "assigned_to": "strategist",
                "artifact_type": "doc",
                "xp_reward": 15
            },
            {
                "id": "step_2_landing_page",
                "title": "Draft and Validate Your Landing Page Structure",
                "description": "Work with the Designer to write a compelling hero headline, copy, and set up a deployment check.",
                "assigned_to": "designer",
                "artifact_type": "url",
                "xp_reward": 25
            },
            {
                "id": "step_3_launch_email",
                "title": "Draft Your Landing Page Launch Campaign",
                "description": "Have the Marketer create a launch outreach or newsletter email, featuring a CTA to drive landing page signups.",
                "assigned_to": "marketer",
                "artifact_type": "email",
                "xp_reward": 20
            }
        ]
        
    quest_state = QuestState(
        id="first_landing_page",
        title="Forge Your First Landing Page",
        description="Fulfill positioning, draft a page, and set up campaign outreach.",
        steps=[QuestStep(**s) for s in steps_data]
    )
    state.active_quest = quest_state
    store.save()
    
    store.log_event("QUEST_START", narrator.name, "Decomposed pitch into active quest-steps.", {"steps": steps_data})
    return {"initialized": True, "state": state.model_dump()}

@app.post("/api/step/execute")
def execute_current_step():
    """Runs outstanding agent calculations and validation on the currently active step."""
    state = store.load()
    if not state or not state.active_quest:
        raise HTTPException(status_code=400, detail="Game session not initialized. Post to /api/init first.")
        
    quest = state.active_quest
    if quest.current_step_index >= len(quest.steps):
        raise HTTPException(status_code=400, detail="All quest-steps completed!")
        
    step = quest.steps[quest.current_step_index]
    
    # Work begins
    step.status = "in-progress"
    store.log_event("STEP_START", step.assigned_to, f"Agent begins work on: {step.title}", {"step_id": step.id})
    store.save()
    
    artifact_data: Dict[str, Any] = {}
    success = False
    val_results: Dict[str, Any] = {}
    
    pitch = state.pitch
    
    try:
        if step.assigned_to == "strategist":
            agent = StrategistAgent()
            artifact_data = agent.formulate_positioning(pitch)
            success, val_results = validate_positioning(artifact_data)
            
        elif step.assigned_to == "designer":
            agent = DesignerAgent()
            positioning = quest.steps[0].artifact_data or {}
            artifact_data = agent.build_page_structure(positioning)
            success, val_results = validate_landing_page(artifact_data)
            
        elif step.assigned_to == "marketer":
            agent = MarketerAgent()
            positioning = quest.steps[0].artifact_data or {}
            page_structure = quest.steps[1].artifact_data or {}
            artifact_data = agent.draft_launch_email(positioning, page_structure)
            success, val_results = validate_marketing_email(artifact_data)
            
        step.artifact_data = artifact_data
        step.validation_results = val_results
        
        store.log_event("STEP_COMPLETED_REASONING", step.assigned_to, f"Artifact created. Verification gate waiting for review.", {
            "artifact": artifact_data,
            "validation_results": val_results
        })
        store.save()
        
    except Exception as e:
        step.status = "failed"
        store.log_event("STEP_EXECUTION_ERROR", "system", f"Failed executing step reasoning: {str(e)}")
        store.save()
        raise HTTPException(status_code=500, detail=f"Agent Execution Failure: {str(e)}")
        
    return {"state": state.model_dump(), "current_step": step.model_dump()}

@app.post("/api/step/approve")
def approve_current_step():
    """Approves the currently active step, awards XP, and advances step index."""
    state = store.load()
    if not state or not state.active_quest:
        raise HTTPException(status_code=400, detail="Game session not initialized.")
        
    quest = state.active_quest
    idx = quest.current_step_index
    if idx >= len(quest.steps):
        raise HTTPException(status_code=400, detail="All steps already finalized.")
        
    step = quest.steps[idx]
    
    # Award reward and advance
    step.status = "completed"
    state.xp += step.xp_reward
    
    store.log_event("STEP_APPROVED", "human_verifier", f"Approved step {step.id}. XP reward added.", {
        "xp_added": step.xp_reward,
        "total_xp": state.xp
    })
    
    # Check leveling up
    if state.xp >= 50 and state.level == 1:
        state.level += 1
        store.log_event("LEVEL_UP", "system", f"StartUp Level Up! Advanced to level {state.level}", {"xp": state.xp})
    elif state.xp >= 100 and state.level == 2:
        state.level += 1
        store.log_event("LEVEL_UP", "system", f"StartUp Level Up! Advanced to level {state.level}", {"xp": state.xp})
        
    # Move index forward
    quest.current_step_index += 1
    
    if quest.current_step_index >= len(quest.steps):
        quest.status = "completed"
        state.stage = "validated"
        store.log_event("QUEST_LINE_COMPLETED", "system", "First Landing Page questline has been fully accomplished! Stage upgraded to 'validated'.")
        
    store.save()
    return {"state": state.model_dump()}

@app.post("/api/step/reject")
def reject_current_step(feedback: Optional[str] = Body(default=None, embed=True)):
    """Rejects the current step, moving it back to not-started for refactoring."""
    state = store.load()
    if not state or not state.active_quest:
        raise HTTPException(status_code=400, detail="Game session not initialized.")
        
    quest = state.active_quest
    idx = quest.current_step_index
    if idx >= len(quest.steps):
        raise HTTPException(status_code=400, detail="All steps already finalized.")
        
    step = quest.steps[idx]
    step.status = "not-started"
    
    store.log_event("STEP_REJECTED", "human_verifier", f"Rejected artifact for {step.id}. Strategic feedback recorded.", {
        "human_feedback": feedback or "No comments detailed."
    })
    
    store.save()
    return {"state": state.model_dump()}

@app.post("/api/reset")
def reset_game():
    """Resets the state file."""
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except Exception:
            pass
    store.state = None
    return {"success": True, "message": "State reset successfully."}

# Mount static folder for UI
UI_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
os.makedirs(UI_DIRECTORY, exist_ok=True)

# Mount '/' to return index.html, static files, etc.
app.mount("/game", StaticFiles(directory=UI_DIRECTORY, html=True), name="ui")

@app.get("/")
def read_root():
    """Redirects to the UI page."""
    return FileResponse(os.path.join(UI_DIRECTORY, "index.html"))
