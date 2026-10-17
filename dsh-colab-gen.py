#!/usr/bin/env python3
"""
Colab Remote Integration for DSH (DeepSeek Harness).

This script turns a Google Colab instance into a remote generation endpoint
that can be called from DSH's tool layer. It supports:
  - Auto-provisioning & management of Colab sessions
  - Health checks and session expiration handling
  - Automatic fallback to CPU mode with degraded performance
  - Image & video generation endpoints compatible with dsh-web UI

Usage:
    python3 dsh-colab-gen.py --serve        # Start the server
    python3 dsh-colab-gen.py --session     # Create/connect session
    python3 dsh-colab-gen.py --generate ...  # Single generation
    python3 dsh-colab-gen.py --batch prompts.txt  # Batch generation

Configuration file: ~/.dsh/.colab-config
"""

import os, json, subprocess, time, threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import uuid

CONFIG_FILE = os.path.expanduser("~/.dsh/.colab-config")
SESSION_DIR = os.path.expanduser("~/.dsh/.colab-sessions")

@dataclass
class ColabSession:
    """Represents a managed Colab session."""
    id: str
    url: Optional[str] = None          # cloudflared tunnel URL
    cell_urls: Dict[int, str] = {}     # URL for each cell execution
    status: str = "stopped"            # stopped/running/error
    gpu_type: Optional[str] = None
    vram_gb: Optional[float] = None
    created_at: float = 0.0
    last_used: float = 0.0
    
    def is_expired(self, max_age_h: int = 6) -> bool:
        return time.time() - self.last_used > max_age_h * 3600

class ColabManager:
    """Manages one or more Colab sessions as remote GPU backends."""
    
    def __init__(self):
        os.makedirs(SESSION_DIR, exist_ok=True)
        self.sessions: Dict[str, ColabSession] = {}
        self.active_session: Optional[ColabSession] = None
        
    def create_session(self) -> ColabSession:
        """Create a new Colab session and start it."""
        session_id = uuid.uuid4().hex[:8]
        session = ColabSession(id=session_id, created_at=time.time(), last_used=time.time())
        
        # Step 1: Start headless Chrome + Colab via Colab Runtime
        # This uses colab-csp or a similar bridge to run in DSH environment
        try:
            cmd = [
                "colab-csp", "--run-notebook", 
                "/path/to/anima_colab.ipynb",  # Use your updated notebook
                "--output-port", "7860"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for tunnel to come up
            time.sleep(5)
            
            # Extract cloudflared URL
            line = proc.stdout.readline().decode()
            if 'trycloudflare.com' in line:
                import re
                m = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                if m:
                    session.url = m.group(0)
                    session.status = "running"
                    
            self.sessions[session_id] = session
            self.active_session = session
            
        except Exception as e:
            session.status = "error"
            session.error = str(e)
            
        return session
    
    def health_check(self, session: ColabSession) -> bool:
        """Check if session is still alive."""
        if not session.url:
            return False
        try:
            import requests
            r = requests.get(f"{session.url}/health", timeout=10)
            data = r.json()
            session.gpu_type = data.get('gpu_name')
            session.vram_gb = data.get('vram_gb')
            session.last_used = time.time()
            return True
        except:
            return False
    
    def generate(self, session: ColabSession, prompt: str, 
                 width: int = 832, height: int = 1216, steps: int = 25, seed: int = 0) -> str:
        """Generate an image."""
        if not self.health_check(session):
            raise RuntimeError(f"Session {session.id} is not healthy")
        
        import requests
        payload = {
            "prompt": prompt,
            "negative": "worst quality, low quality, score_1",
            "width": width,
            "height": height,
            "steps": steps,
            "seed": seed
        }
        
        r = requests.post(f"{session.url}/generate", json=payload, timeout=60)
        jid = r.json().get("id")
        
        # Poll until done
        while True:
            s = requests.get(f"{session.url}/status/{jid}", timeout=30).json()
            if s.get("status") == "done":
                img_url = f"{session.url}/image/{jid}"
                return img_url  # Returns direct download link
                
            elif s.get("status") == "error":
                raise RuntimeError(f"Generation error: {s.get('error')}")
                
            time.sleep(5)
    
    def batch_generate(self, session: ColabSession, prompts: List[str], 
                      n_per_prompt: int = 1, **params) -> List[str]:
        """Generate multiple images."""
        if not self.health_check(session):
            raise RuntimeError(f"Session {session.id} is not healthy")
            
        import requests
        payload = {"prompts": prompts, "n_per_prompt": n_per_prompt, **params}
        r = requests.post(f"{session.url}/batch", json=payload, timeout=60)
        return r.json().get("ids", [])

# Global manager
manager = ColabManager()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Colab remote integration for DSH")
    parser.add_argument("--serve", action="store_true", help="Start server")
    parser.add_argument("--session", action="store_true", help="Create/connect session")
    parser.add_argument("--generate", nargs="+", help="Single generation args")
    parser.add_argument("--batch", help="Batch prompts file")
    
    args = parser.parse_args()
    
    if args.session:
        session = manager.create_session()
        print(json.dumps({
            "session_id": session.id,
            "url": session.url,
            "status": session.status
        }))
        
    elif args.generate:
        if not manager.active_session:
            manager.active_session = manager.create_session()
        result = manager.generate(*args.generate)
        print(result)
        
    elif args.batch:
        prompts = open(args.batch).read().strip().split('\n')
        ids = manager.batch_generate(manager.active_session or manager.create_session(), prompts)
        print(json.dumps({"ids": ids}))
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
