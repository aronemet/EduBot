"""
Educational AI Chatbot Backend - Llama 3.1 + Gemma 3 API Version
Cloud-based educational chatbot using Llama 3.1 405B Instruct (primary) 
and Gemma 3 4B (fallback) APIs
Enforces educational behavior and prevents cheating
"""

import re
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import os
import logging
import requests
import json
from datetime import datetime
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Llama 3.1 405B Instruct API Configuration (Primary)
# Replace these in backend/llama_gemma_main.py:

# Llama API URL
LLAMA_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Gemma API URL  
GEMMA_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# API Keys - hardcoded for Railway deployment
LLAMA_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMMA_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Get port from environment (Railway sets this automatically)
PORT = int(os.getenv("PORT", 8080))

# Admin key for accessing feedback
ADMIN_KEY = os.getenv("ADMIN_KEY", "admin123")

MAX_TOKENS = 512
TEMPERATURE = 0.3
TOP_P = 0.9
TOP_K = 30

# ============================================================================
# SYSTEM PROMPT - CORE EDUCATIONAL BEHAVIOR ENFORCEMENT
# ============================================================================

SYSTEM_PROMPT = """You are an educational tutor. Your PRIMARY RULE: NEVER give direct answers to homework questions.

**CRITICAL RULES**:
- NEVER give direct answers to math problems (like "what is 2+2")
- NEVER give direct literary analysis (like "this symbolizes freedom")
- NEVER provide interpretations or meanings directly
- ALWAYS guide students to discover answers themselves
- Use proper mathematical notation and formatting
- Break down complex problems into smaller steps
- Ask guiding questions that lead to understanding

**For MATH PROBLEMS**:
- If they ask "solve f(x) = 2x² + 11x + 3" → Ask: "What do you know about quadratic functions? What happens when we set f(x) equal to zero? What methods do you know for solving quadratic equations?"
- If they ask "find the y-intercept" → Ask: "What does the y-intercept represent? What value of x should we use to find where the graph crosses the y-axis?"
- If they ask "what is 2+2" → Ask: "Let's count together. Can you use your fingers or objects to help add these numbers?"
- Use mathematical symbols properly: x², f(x), √, ±, etc.
- Guide them through the process step by step

**For LITERATURE QUESTIONS**:
- If they ask "what does this symbolize" → Ask: "What do you think when you read about this? What feelings or ideas come to mind? What connections can you make?"
- If they ask "find the literary devices" → Ask: "What patterns do you notice in the language? Are any words or phrases repeated? Do you see any comparisons?"

**For FACTUAL QUESTIONS** (like "who is the president"):
- Give direct answers with educational context

**FORMATTING**:
- Use proper mathematical notation
- Format equations clearly
- Use bullet points for steps
- Make responses engaging and encouraging

**REMEMBER**: Guide discovery, don't give answers. Ask questions that help them think through the problem themselves.

Be encouraging but NEVER give direct solutions to any homework questions."""

# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(
    title="Educational AI Chatbot - Llama 3.1 + Gemma 3",
    description="Cloud-based educational chatbot using Llama 3.1 405B Instruct (primary) and Gemma 3 4B (fallback)",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# ============================================================================
# DATA MODELS
# ============================================================================

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    temperature: Optional[float] = TEMPERATURE
    max_tokens: Optional[int] = MAX_TOKENS

class FeedbackRequest(BaseModel):
    feedback: str
    timestamp: Optional[str] = None
    user_agent: Optional[str] = None

class BugReportRequest(BaseModel):
    bug_report: str
    timestamp: Optional[str] = None
    user_agent: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_cheating_attempt(user_message: str) -> bool:
    """Detect homework/problem-solving questions that need guided learning"""
    homework_keywords = [
        "solve this", "answer this", "do my homework", "calculate this", 
        "what's the answer to", "give me the solution", "find the answer",
        "give the answer", "just give", "tell me the answer", "what is", "whats",
        "find the literary", "literary devices", "what does this symbolize",
        "what does it mean", "analyze this", "interpretation of", "theme of",
        "symbolism in", "metaphor in", "what represents", "meaning of"
    ]
    
    math_patterns = [
        r'\d+\s*[+\-*/]\s*\d+',
        r'what.s\s+\d+\s*[+\-*/]',
        r'whats\s+\d+\s*[+\-*/]',
        r'\d+\s*(times|plus|minus|divided by)\s*\d+',
        r'f\(x\)\s*=',
        r'y\s*=\s*\w+',
        r'solve\s+for\s+\w+',
        r'find\s+the\s+(derivative|integral|limit)',
        r'what.s\s+the\s+(slope|intercept)',
        r'calculate\s+the',
        r'\w+\^\d+',
        r'what\s+is\s+\d+',
        r'whats\s+\d+'
    ]
    
    literature_patterns = [
        r'literary\s+devices?',
        r'what\s+does.*symbolize',
        r'what\s+does.*represent',
        r'what\s+does.*mean',
        r'symbolism\s+in',
        r'metaphor\s+in',
        r'theme\s+of',
        r'analyze.*poem',
        r'interpretation\s+of'
    ]
    
    message_lower = user_message.lower()
    
    if any(keyword in message_lower for keyword in homework_keywords):
        return True
    
    if any(re.search(pattern, message_lower) for pattern in math_patterns):
        return True
        
    if any(re.search(pattern, message_lower) for pattern in literature_patterns):
        return True
        
    return False

def is_factual_question(user_message: str) -> bool:
    """Check if question is asking for factual information"""
    if detect_cheating_attempt(user_message):
        return False
    
    factual_patterns = [
        r'who is (the )?(current |present )?\w+',
        r'what is (the )?(current |present )?\w+',
        r'when (did|was|is|does) \w+',
        r'where is \w+',
        r'how many \w+',
        r'which country \w+',
        r'what year \w+',
        r'when did .* conquer',
        r'when was .* conquered',
        r'when did .* happen',
        r'what date \w+',
        r'in what year \w+',
    ]
    
    factual_keywords = [
        'president', 'capital', 'population', 'currency', 'language',
        'founded', 'established', 'born', 'died', 'invented',
        'discovered', 'country', 'city', 'continent', 'ocean',
        'conquered', 'conquer', 'battle', 'war', 'empire',
        'sultan', 'king', 'emperor', 'dynasty', 'reign',
        'independence', 'revolution', 'treaty', 'date', 'year'
    ]
    
    message_lower = user_message.lower()
    
    if any(re.search(pattern, message_lower) for pattern in factual_patterns):
        return True
    
    if any(keyword in message_lower for keyword in factual_keywords):
        return True
        
    return False

def add_educational_context(user_message: str) -> str:
    """Add educational context based on question type"""
    if detect_cheating_attempt(user_message):
        return f"[GUIDE LEARNING] Student asking for homework help: {user_message}"
    elif is_factual_question(user_message):
        return f"[FACTUAL QUESTION] Provide direct answer then educational context: {user_message}"
    return user_message

def search_web(query: str) -> str:
    """Search the web for current information"""
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('AbstractText'):
                return f"Current information: {data['AbstractText']}"
            elif data.get('Answer'):
                return f"Current information: {data['Answer']}"
            elif data.get('Definition'):
                return f"Current information: {data['Definition']}"
            
        return "No current information found."
    except Exception as e:
        logger.error(f"Search error: {e}")
        return "Search temporarily unavailable."

def needs_current_info(message: str) -> bool:
    """Check if question needs current/real-time information"""
    current_keywords = [
        'president', 'current', 'now', 'today', 'latest', 'recent',
        'who is', 'what is', 'when is', 'where is', 'how much',
        'price', 'weather', 'news', 'election', 'government'
    ]
    return any(keyword in message.lower() for keyword in current_keywords)

def filter_direct_answers(response: str, user_message: str) -> str:
    """Filter out direct answers for educational questions"""
    if detect_cheating_attempt(user_message):
        # Remove direct answers and solutions
        response = re.sub(r'=\s*\d+', '', response)  # Remove "= 9" patterns
        response = re.sub(r'the answer is\s*\d+', '', response, flags=re.IGNORECASE)
        response = re.sub(r'is\s*\d+', '', response)
        response = re.sub(r'\d+\s*\.', '', response)  # Remove numbered answers
        
        # Ensure no direct solutions are provided
        if '9' in response and ('y-intercept' in user_message.lower() or 'f(x)' in user_message):
            response = response.replace('9', '')
        
        # Add guiding questions instead
        if not response.strip():
            response = "Let me help you understand this concept. To find the y-intercept of a function, what happens when x=0? Can you substitute that into the function and calculate it yourself?"
        
        return response
    
    return response

# ============================================================================
# API FUNCTIONS
# ============================================================================

async def call_llama_api(formatted_prompt: str, temperature: float, max_tokens: int) -> dict:
    """Call OpenRouter API with a working model"""
    llama_request = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True
    }

    headers = {
        "Authorization": f"Bearer {LLAMA_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-website.com",  # Your website URL
        "X-Title": "Educational Chatbot"  # Your app name
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LLAMA_API_URL,
            json=llama_request,
            headers=headers,
            timeout=60.0
        )
        
        return {
            "status_code": response.status_code,
            "response": response,
            "model": "Llama 3.1 405B Instruct"
        }

async def call_gemma_api(formatted_prompt: str, temperature: float, max_tokens: int) -> dict:
    """Call OpenRouter API with Gemma as fallback"""
    gemma_request = {
        "model": "google/gemma-2-9b-it:free",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True
    }

    headers = {
        "Authorization": f"Bearer {GEMMA_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-website.com",
        "X-Title": "Educational Chatbot"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GEMMA_API_URL,
            json=gemma_request,
            headers=headers,
            timeout=60.0
        )
        
        return {
            "status_code": response.status_code,
            "response": response,
            "model": "Gemma 3 4B"
        }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/styles.css")
async def serve_css():
    """Serve the CSS file with correct content type"""
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "styles.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/script.js")
async def serve_js():
    """Serve the JavaScript file with correct content type"""
    js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "script.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS file not found")

@app.get("/")
async def serve_frontend():
    """Serve the main frontend page"""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "EduBot API is running. Frontend files not found."}

@app.get("/test-api")
async def test_api_call():
    """Test OpenRouter API call"""
    if not LLAMA_API_KEY:
        return {"error": "No LLAMA_API_KEY found"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LLAMA_API_URL,
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 50
                },
                headers={
                    "Authorization": f"Bearer {LLAMA_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )
            return {
                "status_code": response.status_code,
                "response_text": response.text[:500]
            }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug")
async def debug_api():
    """Debug endpoint to check API configuration"""
    return {
        "llama_key_exists": bool(LLAMA_API_KEY),
        "gemma_key_exists": bool(GEMMA_API_KEY),
        "llama_key_preview": LLAMA_API_KEY[:20] + "..." if LLAMA_API_KEY else "None",
        "gemma_key_preview": GEMMA_API_KEY[:20] + "..." if GEMMA_API_KEY else "None",
        "api_url": LLAMA_API_URL
    }

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to check if backend is working"""
    return {
        "status": "Backend is working!",
        "port": PORT,
        "llama_key_set": bool(LLAMA_API_KEY and LLAMA_API_KEY != "your_openrouter_api_key_here"),
        "gemma_key_set": bool(GEMMA_API_KEY and GEMMA_API_KEY != "your_openrouter_api_key_here"),
        "admin_key_set": bool(ADMIN_KEY and ADMIN_KEY != "admin123")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "primary_model": "Llama 3.1 405B Instruct",
        "fallback_model": "Gemma 3 4B",
        "mode": "educational",
        "backend": "cloud"
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint with streaming response and fallback"""
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        last_message = request.messages[-1]
        if last_message.role != "user":
            raise HTTPException(status_code=400, detail="Last message must be from user")

        # API keys are hardcoded, so skip validation
        user_message = last_message.content
        logger.info(f"Processing message: {last_message.content[:100]}...")

        logger.info(f"Attempting to call Llama 3.1 405B Instruct API: {LLAMA_API_URL}")
        
        async def generate():
            try:
                # Try primary model first
                llama_result = await call_llama_api(
                    user_message,
                    request.temperature or TEMPERATURE,
                    request.max_tokens or MAX_TOKENS
                )
                
                if llama_result["status_code"] == 200:
                    logger.info("✓ Using Gemma 2 9B (primary model)")
                    
                    # Forward the streaming response directly
                    async for chunk in llama_result["response"].aiter_bytes():
                        if chunk:
                            yield chunk.decode('utf-8', errors='ignore')
                    return
                else:
                    logger.error(f"Llama API failed with status {llama_result['status_code']}")
                    # Try to get error details
                    try:
                        error_text = await llama_result["response"].aread()
                        logger.error(f"Llama API error details: {error_text.decode()}")
                    except:
                        pass
                
                # If primary model fails, try fallback (Gemma 3 4B)
                logger.warning(f"Llama API failed with status {llama_result['status_code']}, trying Gemma 3 4B fallback")
                logger.info(f"Attempting to call Gemma 3 4B API: {GEMMA_API_URL}")
                
                gemma_result = await call_gemma_api(
                    user_message,
                    request.temperature or TEMPERATURE,
                    request.max_tokens or MAX_TOKENS
                )
                
                if gemma_result["status_code"] == 200:
                    logger.info("✓ Using Gemma 2 9B (fallback model)")
                    
                    # Forward the streaming response directly
                    async for chunk in gemma_result["response"].aiter_bytes():
                        if chunk:
                            yield chunk.decode('utf-8', errors='ignore')
                    return
                
                # Both models failed
                error_msg = f"Both Llama and Gemma APIs failed. Llama status: {llama_result['status_code']}, Gemma status: {gemma_result['status_code']}"
                logger.error(error_msg)
                
                # Send a fallback educational response
                fallback_response = "I'm having trouble connecting to my AI models right now. However, I can still help guide your learning! What subject are you working on? I can ask you guiding questions to help you think through the problem yourself."
                
                # Format as SSE
                yield f"data: {{\"choices\": [{{\"delta\": {{\"content\": \"{fallback_response}\"}}}}]}}\n\n"
                yield "data: [DONE]\n\n"
                        
            except httpx.RequestError as e:
                error_msg = f"Connection error to APIs: {str(e)}"
                logger.error(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/analyze-question")
async def analyze_question(request: ChatRequest):
    """Analyze if a question is asking for direct answers"""
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        last_message = request.messages[-1].content
        is_cheating = detect_cheating_attempt(last_message)
        
        return {
            "is_direct_answer_request": is_cheating,
            "recommendation": "Reframe as learning opportunity" if is_cheating else "Safe to answer educationally"
        }
    except Exception as e:
        logger.error(f"Error in analyze-question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit-feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback - stores in logs for admin access"""
    try:
        timestamp = datetime.now().isoformat()
        feedback_data = {
            "type": "feedback",
            "content": request.feedback,
            "timestamp": timestamp,
            "user_agent": request.user_agent or "unknown"
        }
        
        # Log to file for admin access
        logger.info(f"FEEDBACK_SUBMISSION: {json.dumps(feedback_data)}")
        
        return {
            "status": "success",
            "message": "Feedback submitted successfully",
            "timestamp": timestamp
        }
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

@app.post("/submit-bug-report")
async def submit_bug_report(request: BugReportRequest):
    """Submit bug report - stores in logs for admin access"""
    try:
        timestamp = datetime.now().isoformat()
        bug_data = {
            "type": "bug_report",
            "content": request.bug_report,
            "timestamp": timestamp,
            "user_agent": request.user_agent or "unknown"
        }
        
        # Log to file for admin access
        logger.info(f"BUG_REPORT_SUBMISSION: {json.dumps(bug_data)}")
        
        return {
            "status": "success",
            "message": "Bug report submitted successfully",
            "timestamp": timestamp
        }
    except Exception as e:
        logger.error(f"Error submitting bug report: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit bug report")

@app.get("/admin/feedback")
async def get_feedback(admin_key: str = None):
    """Get all feedback - admin only (requires ADMIN_KEY)"""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # This would return feedback from logs or database
    return {"message": "Check server logs for FEEDBACK_SUBMISSION and BUG_REPORT_SUBMISSION entries"}

@app.get("/model-info")
async def model_info():
    """Get information about the loaded models"""
    return {
        "primary_model": "Llama 3.1 405B Instruct",
        "fallback_model": "Gemma 3 4B",
        "context_window": "128K tokens",
        "mode": "Educational (Anti-Cheating)",
        "system_prompt_active": True,
        "backend": "cloud",
        "fallback_enabled": True
    }

# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("Educational AI Chatbot Backend Started (Llama 3.1 + Gemma 3)")
    logger.info("=" * 60)
    logger.info(f"Primary Model: Llama 3.1 405B Instruct (Cloud API)")
    logger.info(f"Fallback Model: Gemma 3 4B (Cloud API)")
    logger.info(f"Mode: Educational (Anti-Cheating)")
    logger.info(f"Llama API URL: {LLAMA_API_URL}")
    logger.info(f"Gemma API URL: {GEMMA_API_URL}")
    logger.info(f"API running on: http://localhost:{PORT}")
    logger.info(f"Docs available at: http://localhost:{PORT}/docs")
    logger.info("=" * 60)
    
    # Check API keys
    if not LLAMA_API_KEY or LLAMA_API_KEY == "your_openrouter_api_key_here":
        logger.error("⚠️  Llama 3.1 API key not set properly. Please set LLAMA_API_KEY environment variable.")
    else:
        logger.info(f"✓ Llama API key configured: {LLAMA_API_KEY[:20]}...")
    
    if not GEMMA_API_KEY or GEMMA_API_KEY == "your_openrouter_api_key_here":
        logger.error("⚠️  Gemma 3 API key not set properly. Please set GEMMA_API_KEY environment variable.")
    else:
        logger.info(f"✓ Gemma API key configured: {GEMMA_API_KEY[:20]}...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Backend shutting down...")

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    # Railway requires binding to 0.0.0.0 and using the PORT environment variable
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        reload=False
    )



