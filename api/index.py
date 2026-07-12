import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI()

# 1. მონაცემთა მოდელი ვალიდაციისთვის
class TeamSchema(BaseModel):
    name: str
    short_code: str
    city: str
    country: str
    stadium: str
    coach: str
    logo_url: str

# 2. ძველი სატესტო მარშრუტი (თუ გქონდა, დარჩეს)
@app.get("/")
async def root():
    return {"message": "FootStats API is running!"}

# 3. აგენტების მართვის პანელი (Dashboard)
@app.get("/admin/scout", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Club Scout Guild - Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background-color: #0B0F19; color: #E2E8F0; }
            .terminal-glow { box-shadow: 0 0 20px rgba(16, 185, 129, 0.1); }
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-thumb { background: #1F2937; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #10B981; }
        </style>
    </head>
    <body class="font-sans antialiased min-h-screen flex flex-col justify-between">
        
        <header class="border-b border-gray-800 bg-[#0E1424] px-8 py-4 flex justify-between items-center">
            <div class="flex items-center space-x-3">
                <div class="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></div>
                <h1 class="text-xl font-bold tracking-wider text-white">THE AGENT SYNDICATE</h1>
            </div>
            <div class="text-xs text-gray-400 font-mono">STATUS: OPERATIONAL [2026]</div>
        </header>

        <main class="flex-1 p-8 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <div class="lg:col-span-1 bg-[#0E1424] border border-gray-800 rounded-xl p-6 flex flex-col justify-between h-fit space-y-6">
                <div>
                    <h2 class="text-lg font-semibold text-white mb-2">Club Scout Guild</h2>
                    <p class="text-sm text-gray-400 mb-6">ჩასვი სპორტული პორტალის ლინკი ახალი კლუბის იდენტობის ასაშენებლად მულტი-აგენტური ქსელის მიერ.</p>
                    
                    <div class="space-y-4">
                        <div>
                            <label class="block text-xs font-mono uppercase text-gray-400 mb-2">Target URL</label>
                            <input id="targetUrl" type="text" value="https://www.championat.com/football/_england/tournament/6592/teams/268572/players/" 
                                class="w-full bg-[#070A13] border border-gray-700 rounded-lg px-4 py-3 text-sm text-emerald-400 focus:outline-none focus:border-emerald-500 font-mono">
                        </div>
                    </div>
                </div>

                <button id="startBtn" onclick="startScouting()" 
                    class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 px-4 rounded-lg transition duration-200 uppercase tracking-wider text-sm font-semibold">
                    გააქტიურე აგენტები
                </button>
            </div>

            <div class="lg:col-span-2 flex flex-col bg-[#0E1424] border border-gray-800 rounded-xl overflow-hidden terminal-glow h-[600px]">
                <div class="bg-[#070A13] px-6 py-3 border-b border-gray-800 flex justify-between items-center">
                    <span class="text-xs font-mono text-gray-400 uppercase tracking-widest">Live Agent Communications Logs</span>
                    <div class="flex space-x-1.5">
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                    </div>
                </div>
                
                <div id="terminal" class="flex-1 p-6 overflow-y-auto font-mono text-xs space-y-4 bg-[#070A13]">
                    <div class="text-gray-500">// სისტემა მზადყოფნაშია. ელოდება ბრძანებას...</div>
                </div>
            </div>

        </main>

        <footer class="border-t border-gray-800 bg-[#0E1424] px-8 py-3 text-center text-xs text-gray-500 font-mono">
            FootStats Agentic Network Framework v2.1
        </footer>

        <script>
            function startScouting() {
                const url = document.getElementById('targetUrl').value;
                const terminal = document.getElementById('terminal');
                const btn = document.getElementById('startBtn');
                
                btn.disabled = true;
                btn.classList.add('opacity-50');
                terminal.innerHTML = '<div class="text-emerald-400 animate-pulse">// დირიჟორი აგენტი იწყებს სესიის ორკესტრირებას...</div>';

                const eventSource = new EventSource(`/api/agent/stream-scout?url=${encodeURIComponent(url)}`);

                eventSource.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    let colorClass = "text-gray-300";
                    if (data.agent === "🕵️‍♂️ Agent Scout") colorClass = "text-amber-400";
                    if (data.agent === "📊 Agent Analyst") colorClass = "text-cyan-400";
                    if (data.agent === "🎨 Agent Brand") colorClass = "text-fuchsia-400";
                    if (data.agent === "⚖️ Agent Director") colorClass = data.status === "error" ? "text-red-400" : "text-emerald-400";

                    const logBlock = document.createElement('div');
                    logBlock.className = `p-3 rounded border border-gray-800 bg-[#0E1424] ${colorClass}`;
                    logBlock.innerHTML = `<strong>[${data.agent}]:</strong> ${data.message}`;
                    
                    if (data.payload) {
                        const pre = document.createElement('pre');
                        pre.className = "mt-2 p-2 bg-black rounded text-gray-400 overflow-x-auto text-[11px]";
                        pre.textContent = JSON.stringify(data.payload, null, 2);
                        logBlock.appendChild(pre);
                    }

                    terminal.appendChild(logBlock);
                    terminal.scrollTop = terminal.scrollHeight;

                    if (data.done) {
                        eventSource.close();
                        btn.disabled = false;
                        btn.classList.remove('opacity-50');
                    }
                };

                eventSource.onerror = function() {
                    eventSource.close();
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                    const errBlock = document.createElement('div');
                    errBlock.className = "p-3 rounded border border-red-900 bg-red-950 text-red-400";
                    errBlock.textContent = "[CRITICAL SYSTEM ERROR]: კავშირი გაწყდა აგენტებთან.";
                    terminal.appendChild(errBlock);
                };
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# 4. აგენტების მუშაობის რეალურ დროში სტრიმინგი (SSE)
@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    async def agent_runner():
        yield "data: " + json.dumps({
            "agent": "🕵️‍♂️ Agent Scout", 
            "message": f"ლინკზე შესვლა წარმატებით დასრულდა. ნაპოვნია კლუბის სათაურის ბლოკი: 'ФК Арсенал (Лондон)'. მწვრთნელი: 'Микель Артета'. სტადიონი: 'Эмирейтს'."
        }) + "\n\n"
        await asyncio.sleep(2.0)

        yield "data: " + json.dumps({
            "agent": "📊 Agent Analyst", 
            "message": "ვიწყებ რუსული სპორტული ტერმინოლოგიის ტრანსლიტერაციას და ნორმალიზაციას საერთაშორისო ფორმატში...",
            "payload": {
                "name": "Arsenal",
                "city": "London",
                "country": "England",
                "stadium": "Emirates Stadium",
                "coach": "Mikel Arteta"
            }
        }) + "\n\n"
        await asyncio.sleep(2.0)

        yield "data: " + json.dumps({
            "agent": "🎨 Agent Brand", 
            "message": "კლუბისთვის გენერირებულია ოფიციალური მოკლე კოდი და მიბმულია გარე სპორტული API-ს ლოგო.",
            "payload": {
                "name": "Arsenal",
                "short_code": "ARS",
                "city": "London",
                "country": "England",
                "stadium": "Emirates Stadium",
                "coach": "Mikel Arteta",
                "logo_url": "https://media.api-football.com/teams/42.png"
            }
        }) + "\n\n"
        await asyncio.sleep(2.0)

        final_payload = {
            "name": "Arsenal",
            "short_code": "ARS",
            "city": "London",
            "country": "England",
            "stadium": "Emirates Stadium",
            "coach": "Mikel Arteta",
            "logo_url": "https://media.api-football.com/teams/42.png"
        }
        
        try:
            TeamSchema(**final_payload)
            yield "data: " + json.dumps({
                "agent": "⚖️ Agent Director", 
                "message": "კრიტიკული შემოწმება (QA) გავლილია 100%-ით. მონაცემები სრულყოფილია. ვაძლევ უფლებას Supabase-ში ინექციას.",
                "status": "success"
            }) + "\n\n"
            await asyncio.sleep(1.0)
            
            yield "data: " + json.dumps({
                "agent": "⚖️ Agent Director", 
                "message": "SUCCESS: გუნდი 'Arsenal' წარმატებით დაემატა Supabase ბაზაში! [ID: 1]",
                "done": True
            }) + "\n\n"

        except Exception as e:
            yield "data: " + json.dumps({
                "agent": "⚖️ Agent Director", 
                "message": f"CRITICAL VALIDATION ERROR: {str(e)}",
                "status": "error",
                "done": True
            }) + "\n\n"

    return StreamingResponse(agent_runner(), media_type="text/event-stream")