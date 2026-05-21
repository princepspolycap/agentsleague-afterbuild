from typing import Dict, Any, List, Optional
import os

class BaseFoundryAgent:
    """
    Simulates a Foundry Agent using local environment variables or mock routing behavior.
    """
    def __init__(self, name: str, role: str, system_instructions: str):
        self.name = name
        self.role = role
        self.system_instructions = system_instructions

    def get_personality_preamble(self) -> str:
        return f"[Agent: {self.name} | Role: {self.role}]\n"

    def execute_reasoning_step(self, prompt: str, search_context: Optional[str] = None) -> str:
        # If AZURE_AI_PROJECT_CONNECTION_STRING is present, actual client code would be initialized here.
        # Otherwise, we output specialized reasoning results tailored to the user's input/scenarios.
        pass

class MasterNarrator(BaseFoundryAgent):
    def __init__(self):
        instructions = (
            "You are the Game Master and Master Narrator of a startup-building RPG game. "
            "Your job is to read a business idea pitch, decompose it into a quest line (with steps for "
            "Strategist, Designer, and Marketer), narrate the outcomes, and maintain the game state."
        )
        super().__init__("The Narrator", "Master Narrator", instructions)

    def decompose_pitch(self, pitch: str) -> List[Dict[str, Any]]:
        """
        Decomposes the company pitch into 3 distinct quest steps.
        """
        return [
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

class StrategistAgent(BaseFoundryAgent):
    def __init__(self):
        super().__init__("Soren", "Strategist", "You are the lean-startup strategist. You specialize in positioning, audience segmentation, and core problem statements.")

    def formulate_positioning(self, pitch: str) -> Dict[str, str]:
        # Formulates high-quality positioning grounded in the pitch
        return {
            "target_audience": "Freelance Web Designers and Small Agency Owners",
            "core_problem": f"Struggle to estimate exact project time and pricing, leading to scope creep and unpaid overtime. Prompt source: {pitch}",
            "value_proposition": "An interactive, metric-driven estimation dashboard that calculates recommended pricing based on historical task-level benchmarks.",
            "primary_benefit": "Bid for projects 2x faster and immediately eliminate unpaid scope-crawl."
        }

class DesignerAgent(BaseFoundryAgent):
    def __init__(self):
        super().__init__("Dahlia", "Designer", "You are the visual and UX designer. You design wireframes, structure hero headers, and direct calls to action.")

    def build_page_structure(self, positioning: Dict[str, str]) -> Dict[str, str]:
        audience = positioning.get("target_audience", "Your Audience")
        benefit = positioning.get("primary_benefit", "Price with confidence.")
        return {
            "hero_headline": f"The Smarter Way for {audience} to Quote and Price Project Scope",
            "cta_text": "Price My Next Project Free",
            "features": "1. Multi-metric Estimator; 2. Client-ready Proposal Export; 3. Scope Crawl Alert System",
            "url": "https://estimator-preview.agencyofpoly.com"
        }

class MarketerAgent(BaseFoundryAgent):
    def __init__(self):
        super().__init__("Maddox", "Marketer", "You are the copywriter and growth marketer. You turn positioning and design assets into high-converting copy.")

    def draft_launch_email(self, positioning: Dict[str, str], page_structure: Dict[str, str]) -> Dict[str, str]:
        target = positioning.get("target_audience", "Freelancer")
        problem = positioning.get("core_problem", "underpricing projects")
        url = page_structure.get("url", "https://estimator-preview.agencyofpoly.com")
        
        return {
            "subject": f"Stop underpricing your next project: A new quoting tool for {target}!",
            "body": (
                f"Hey there,\n\n"
                f"If you're like most {target}, you probably struggle with {problem}.\n\n"
                f"We just designed a new workspace that solves exactly this issue. It includes a "
                f"multi-metric estimator and proposal exporter to save you hours of unpaid work.\n\n"
                f"Check it out and bid faster here:\n[CTA] {url}\n\n"
                f"Best,\nYour Quoting Team"
            )
        }
