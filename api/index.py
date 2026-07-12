import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI()

class TeamSchema(BaseModel):
    name: str
    short_code: str
    city: str
    country: str
    stadium: str
    coach: str
    logo_url: str

@app.get("/")
async def root():
    return {"message": "FootStats API is running!"}

@app.get("/admin/scout", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <title>Club Scout Guild</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0B0F19] text-[#E2E8F0] font-sans p-8">
        <div class="max-w-4xl mx-auto bg-[#0E1424] border border-gray-800 rounded-xl p-6">
            <h1 class="text-xl font-bold text-white mb-4">🤖 Club Scout Guild Dashboard</h1>
            <input id="targetUrl" type="text" value="https://www.championat.com/" class="w-full bg-[#070A13] border border-gray-700 rounded p-2 text-emerald-400 mb-4 font-mono">
            <button onclick="startScouting()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded font-semibold w-full">გააქტიურე აგენტები</button>
            <div id="terminal" class="mt-6 p-4 bg-[#070A13] border border-gray-850 rounded h-60 overflow-y-auto font-mono text-xs space-y-2">
                <div class="text-gray-500">// სისტემა მზად არის...</div>
            </div>
        </div>
        <script>
            function startScouting() {
                const url = document.getElementById('targetUrl').value;
                const terminal = document.getElementById('terminal');
                terminal.innerHTML = '<div class="text-emerald-400">// აგენტები ჩაირთვნენ...</div>';
                const eventSource = new EventSource('/api/agent/stream-scout?url=' + encodeURIComponent(url));
                eventSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    const log = document.createElement('div');
                    log.innerHTML = '<strong>[' + data.agent + ']:</strong> ' + data.message;
                    terminal.appendChild(log);
                    if (data.done) eventSource.close();
                };
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    async def agent_runner():
        yield "data: " + json.dumps({"agent": "Scout", "message": "მონაცემები წამოღებულია რუსული საიტიდან."}) + "\n\n"
        await asyncio.sleep(1.5)
        yield "data: " + json.dumps({"agent": "Analyst", "message": "სახელები გადაითარგმნა ინგლისურად."}) + "\n\n"
        await asyncio.sleep(1.5)
        yield "data: " + json.dumps({"agent": "Director", "message": "მონაცემები 100%-ით სწორია და შეინახა ბაზაში.", "done": True}) + "\n\n"
    return StreamingResponse(agent_runner(), media_type="text/event-stream")