@app.get("/admin/scout", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 FootStats Agent Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes pulse-glow {
                0%, 100% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.5); }
                50% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.8); }
            }
            .agent-active {
                animation: pulse-glow 2s infinite;
            }
            .log-entry {
                animation: slideIn 0.3s ease-out;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateX(-10px); }
                to { opacity: 1; transform: translateX(0); }
            }
            .step-completed {
                border-left: 4px solid #10b981;
            }
            .step-active {
                border-left: 4px solid #f59e0b;
            }
            .step-pending {
                border-left: 4px solid #6b7280;
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen p-6">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">🤖 FootStats Agent Dashboard</h1>
                <p class="text-gray-400">ავტომატიზებული საფეხბურთო სტატისტიკის სისტემა</p>
            </div>

            <!-- Agent Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <!-- TeamScout Card -->
                <div id="scout-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-emerald-600 rounded-full flex items-center justify-center text-2xl">🕵️</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">TeamScout</h2>
                                <p class="text-sm text-gray-400">მზვერავი აგენტი</p>
                            </div>
                        </div>
                        <div id="scout-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">აგროვებს გუნდის ინფორმაციას სპორტული საიტებიდან</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="scout-task" class="text-emerald-400">მოლოდინში</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-500">ბოლო მოპოვება:</span>
                            <span id="scout-last" class="text-gray-400">არ არის</span>
                        </div>
                    </div>
                </div>

                <!-- Controller Card -->
                <div id="controller-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-2xl">🛡️</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">Controller</h2>
                                <p class="text-sm text-gray-400">მაკონტროლებელი აგენტი</p>
                            </div>
                        </div>
                        <div id="controller-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">ამოწმებს მონაცემებს და ინახავს ბაზაში</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="controller-task" class="text-blue-400">მოლოდინში</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-500">შემოწმებული:</span>
                            <span id="controller-checked" class="text-gray-400">0 გუნდი</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Input Section -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">🎯 გუნდის URL</h3>
                <div class="flex gap-3">
                    <input 
                        id="targetUrl" 
                        type="text" 
                        value="https://www.championat.com/football/_england/tournament/6592/teams/268572/"
                        placeholder="ჩაწერე გუნდის URL championat.com-დან" 
                        class="flex-1 bg-[#070A13] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-sm focus:outline-none focus:border-emerald-500"
                    >
                    <button 
                        onclick="startScouting()" 
                        id="startBtn"
                        class="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        🚀 გააქტიურე
                    </button>
                </div>
            </div>

            <!-- Process Steps -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 პროცესის ნაბიჯები</h3>
                <div class="space-y-3">
                    <div id="step-1" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">1</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">მონაცემების მოპოვება</div>
                                <div class="text-xs text-gray-400">TeamScout აგროვებს ინფორმაციას საიტიდან</div>
                            </div>
                            <div id="step-1-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-2" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">2</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">ვალიდაცია</div>
                                <div class="text-xs text-gray-400">Controller ამოწმებს მონაცემების სისწორეს</div>
                            </div>
                            <div id="step-2-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-3" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">3</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">ბაზაში ჩაწერა</div>
                                <div class="text-xs text-gray-400">მონაცემები ინახება Supabase-ში</div>
                            </div>
                            <div id="step-3-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Live Logs -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#070A13] border border-gray-850 rounded-lg p-4 h-80 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის. დაელოდე ბრძანებას...</div>
                </div>
            </div>
        </div>

        <script>
            let checkedCount = 0;

            function startScouting() {
                const url = document.getElementById('targetUrl').value;
                const startBtn = document.getElementById('startBtn');
                
                if (!url) {
                    alert('გთხოვთ ჩაწეროთ URL');
                    return;
                }

                // Disable button
                startBtn.disabled = true;
                startBtn.textContent = '⏳ მუშაობს...';

                // Reset UI
                resetUI();
                
                // Start streaming
                const eventSource = new EventSource('/api/agent/stream-scout?url=' + encodeURIComponent(url));
                
                eventSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    handleAgentMessage(data);
                    
                    if (data.done) {
                        eventSource.close();
                        startBtn.disabled = false;
                        startBtn.textContent = '🚀 გააქტიურე';
                    }
                };

                eventSource.onerror = function(e) {
                    addLog('system', '❌ კავშირი დაიკარგა', 'error');
                    eventSource.close();
                    startBtn.disabled = false;
                    startBtn.textContent = '🚀 გააქტიურე';
                };
            }

            function resetUI() {
                // Clear logs
                document.getElementById('terminal').innerHTML = '';
                
                // Reset steps
                for (let i = 1; i <= 3; i++) {
                    const step = document.getElementById(`step-${i}`);
                    step.className = 'step-pending bg-[#070A13] rounded-lg p-4 transition-all';
                    document.getElementById(`step-${i}-status`).textContent = '⏸️';
                }

                // Reset agent cards
                document.getElementById('scout-card').classList.remove('agent-active');
                document.getElementById('controller-card').classList.remove('agent-active');
                document.getElementById('scout-status').innerHTML = '⏸️ მზად';
                document.getElementById('scout-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
                document.getElementById('controller-status').innerHTML = '⏸️ მზად';
                document.getElementById('controller-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
            }

            function handleAgentMessage(data) {
                const { agent, message, step, status, team_name } = data;

                // Add log
                const logType = message.includes('❌') ? 'error' : 
                               message.includes('✅') ? 'success' : 
                               message.includes('⚠️') ? 'warning' : 'info';
                addLog(agent, message, logType);

                // Update agent cards
                if (agent === 'TeamScout') {
                    document.getElementById('scout-card').classList.add('agent-active');
                    document.getElementById('scout-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('scout-task').textContent = message.substring(0, 30) + '...';
                    
                    if (team_name) {
                        document.getElementById('scout-last').textContent = team_name;
                    }
                } else if (agent === 'Controller') {
                    document.getElementById('controller-card').classList.add('agent-active');
                    document.getElementById('controller-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('controller-task').textContent = message.substring(0, 30) + '...';
                }

                // Update steps
                if (step) {
                    updateStep(step, status);
                }

                // Handle completion
                if (data.done) {
                    document.getElementById('scout-card').classList.remove('agent-active');
                    document.getElementById('controller-card').classList.remove('agent-active');
                    document.getElementById('scout-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold';
                    document.getElementById('controller-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold';
                    
                    checkedCount++;
                    document.getElementById('controller-checked').textContent = `${checkedCount} გუნდი`;
                }
            }

            function updateStep(stepNum, status) {
                const step = document.getElementById(`step-${stepNum}`);
                const statusEl = document.getElementById(`step-${stepNum}-status`);

                if (status === 'active') {
                    step.className = 'step-active bg-[#070A13] rounded-lg p-4 transition-all';
                    statusEl.textContent = '🔄';
                } else if (status === 'completed') {
                    step.className = 'step-completed bg-[#070A13] rounded-lg p-4 transition-all';
                    statusEl.textContent = '✅';
                } else if (status === 'error') {
                    step.className = 'bg-red-900/20 border border-red-500 rounded-lg p-4 transition-all';
                    statusEl.textContent = '❌';
                }
            }

            function addLog(agent, message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';

                const colors = {
                    'info': 'text-blue-400',
                    'success': 'text-emerald-400',
                    'warning': 'text-yellow-400',
                    'error': 'text-red-400',
                    'system': 'text-gray-400'
                };

                const agentColors = {
                    'TeamScout': 'text-emerald-400',
                    'Controller': 'text-blue-400',
                    'system': 'text-gray-500'
                };

                const timestamp = new Dimport asyncio
import json
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from team_scout import TeamScout
from controller_bot import ControllerBot

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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 FootStats Agent Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes pulse-glow {
                0%, 100% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.5); }
                50% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.8); }
            }
            .agent-active {
                animation: pulse-glow 2s infinite;
            }
            .log-entry {
                animation: slideIn 0.3s ease-out;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateX(-10px); }
                to { opacity: 1; transform: translateX(0); }
            }
            .step-completed {
                border-left: 4px solid #10b981;
            }
            .step-active {
                border-left: 4px solid #f59e0b;
            }
            .step-pending {
                border-left: 4px solid #6b7280;
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen p-6">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">🤖 FootStats Agent Dashboard</h1>
                <p class="text-gray-400">ავტომატიზებული საფეხბურთო სტატისტიკის სისტემა</p>
            </div>

            <!-- Agent Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <!-- TeamScout Card -->
                <div id="scout-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-emerald-600 rounded-full flex items-center justify-center text-2xl">🕵️</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">TeamScout</h2>
                                <p class="text-sm text-gray-400">მზვერავი აგენტი</p>
                            </div>
                        </div>
                        <div id="scout-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">აგროვებს გუნდის ინფორმაციას სპორტული საიტებიდან</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="scout-task" class="text-emerald-400">მოლოდინში</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-500">ბოლო მოპოვება:</span>
                            <span id="scout-last" class="text-gray-400">არ არის</span>
                        </div>
                    </div>
                </div>

                <!-- Controller Card -->
                <div id="controller-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-2xl">🛡️</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">Controller</h2>
                                <p class="text-sm text-gray-400">მაკონტროლებელი აგენტი</p>
                            </div>
                        </div>
                        <div id="controller-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">ამოწმებს მონაცემებს და ინახავს ბაზაში</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="controller-task" class="text-blue-400">მოლოდინში</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-500">შემოწმებული:</span>
                            <span id="controller-checked" class="text-gray-400">0 გუნდი</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Input Section -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">🎯 გუნდის URL</h3>
                <div class="flex gap-3">
                    <input 
                        id="targetUrl" 
                        type="text" 
                        value="https://www.championat.com/football/_england/tournament/6592/teams/268572/"
                        placeholder="ჩაწერე გუნდის URL championat.com-დან" 
                        class="flex-1 bg-[#070A13] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-sm focus:outline-none focus:border-emerald-500"
                    >
                    <button 
                        onclick="startScouting()" 
                        id="startBtn"
                        class="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        🚀 გააქტიურე
                    </button>
                </div>
            </div>

            <!-- Process Steps -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 პროცესის ნაბიჯები</h3>
                <div class="space-y-3">
                    <div id="step-1" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">1</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">მონაცემების მოპოვება</div>
                                <div class="text-xs text-gray-400">TeamScout აგროვებს ინფორმაციას საიტიდან</div>
                            </div>
                            <div id="step-1-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-2" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">2</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">ვალიდაცია</div>
                                <div class="text-xs text-gray-400">Controller ამოწმებს მონაცემების სისწორეს</div>
                            </div>
                            <div id="step-2-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-3" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">3</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">ბაზაში ჩაწერა</div>
                                <div class="text-xs text-gray-400">მონაცემები ინახება Supabase-ში</div>
                            </div>
                            <div id="step-3-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Live Logs -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#070A13] border border-gray-850 rounded-lg p-4 h-80 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის. დაელოდე ბრძანებას...</div>
                </div>
            </div>
        </div>

        <script>
            let checkedCount = 0;

            function startScouting() {
                const url = document.getElementById('targetUrl').value;
                const startBtn = document.getElementById('startBtn');
                
                if (!url) {
                    alert('გთხოვთ ჩაწეროთ URL');
                    return;
                }

                // Disable button
                startBtn.disabled = true;
                startBtn.textContent = '⏳ მუშაობს...';

                // Reset UI
                resetUI();
                
                // Start streaming
                const eventSource = new EventSource('/api/agent/stream-scout?url=' + encodeURIComponent(url));
                
                eventSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    handleAgentMessage(data);
                    
                    if (data.done) {
                        eventSource.close();
                        startBtn.disabled = false;
                        startBtn.textContent = '🚀 გააქტიურე';
                    }
                };

                eventSource.onerror = function(e) {
                    addLog('system', '❌ კავშირი დაიკარგა', 'error');
                    eventSource.close();
                    startBtn.disabled = false;
                    startBtn.textContent = '🚀 გააქტიურე';
                };
            }

            function resetUI() {
                // Clear logs
                document.getElementById('terminal').innerHTML = '';
                
                // Reset steps
                for (let i = 1; i <= 3; i++) {
                    const step = document.getElementById(`step-${i}`);
                    step.className = 'step-pending bg-[#070A13] rounded-lg p-4 transition-all';
                    document.getElementById(`step-${i}-status`).textContent = '⏸️';
                }

                // Reset agent cards
                document.getElementById('scout-card').classList.remove('agent-active');
                document.getElementById('controller-card').classList.remove('agent-active');
                document.getElementById('scout-status').innerHTML = '⏸️ მზად';
                document.getElementById('scout-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
                document.getElementById('controller-status').innerHTML = '⏸️ მზად';
                document.getElementById('controller-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
            }

            function handleAgentMessage(data) {
                const { agent, message, step, status, team_name } = data;

                // Add log
                const logType = message.includes('❌') ? 'error' : 
                               message.includes('✅') ? 'success' : 
                               message.includes('⚠️') ? 'warning' : 'info';
                addLog(agent, message, logType);

                // Update agent cards
                if (agent === 'TeamScout') {
                    document.getElementById('scout-card').classList.add('agent-active');
                    document.getElementById('scout-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('scout-task').textContent = message.substring(0, 30) + '...';
                    
                    if (team_name) {
                        document.getElementById('scout-last').textContent = team_name;
                    }
                } else if (agent === 'Controller') {
                    document.getElementById('controller-card').classList.add('agent-active');
                    document.getElementById('controller-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('controller-task').textContent = message.substring(0, 30) + '...';
                }

                // Update steps
                if (step) {
                    updateStep(step, status);
                }

                // Handle completion
                if (data.done) {
                    document.getElementById('scout-card').classList.remove('agent-active');
                    document.getElementById('controller-card').classList.remove('agent-active');
                    document.getElementById('scout-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold';
                    document.getElementById('controller-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold';
                    
                    checkedCount++;
                    document.getElementById('controller-checked').textContent = `${checkedCount} გუნდი`;
                }
            }

            function updateStep(stepNum, status) {
                const step = document.getElementById(`step-${stepNum}`);
                const statusEl = document.getElementById(`step-${stepNum}-status`);

                if (status === 'active') {
                    step.className = 'step-active bg-[#070A13] rounded-lg p-4 transition-all';
                    statusEl.textContent = '🔄';
                } else if (status === 'completed') {
                    step.className = 'step-completed bg-[#070A13] rounded-lg p-4 transition-all';
                    statusEl.textContent = '✅';
                } else if (status === 'error') {
                    step.className = 'bg-red-900/20 border border-red-500 rounded-lg p-4 transition-all';
                    statusEl.textContent = '❌';
                }
            }

            function addLog(agent, message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';

                const colors = {
                    'info': 'text-blue-400',
                    'success': 'text-emerald-400',
                    'warning': 'text-yellow-400',
                    'error': 'text-red-400',
                    'system': 'text-gray-400'
                };

                const agentColors = {
                    'TeamScout': 'text-emerald-400',
                    'Controller': 'text-blue-400',
                    'system': 'text-gray-500'
                };

                const timestamp = new Date().toLocaleTimeString('ka-GE');
                
                log.innerHTML = `
                    <span class="text-gray-600">[${timestamp}]</span>
                    <strong class="${agentColors[agent] || 'text-gray-400'}">[${agent}]</strong>
                    <span class="${colors[type]}">${message}</span>
                `;

                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// ლოგები გასუფთავდა</div>';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    scout = TeamScout()
    controller = ControllerBot()
    
    async def agent_runner():
        # STEP 1: TeamScout მუშაობს
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": "🔍 ვიწყებ მონაცემების მოპოვებას...",
            "step": 1,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"📡 ვუკავშირდები: {url}",
            "step": 1,
            "status": "active"
        }) + "\n\n"
        
        result = await scout.scout_team(url)
        
        if not result["success"]:
            yield "data: " + json.dumps({
                "agent": "TeamScout", 
                "message": f"❌ შეცდომა: {result['error']}",
                "step": 1,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        team_data = result["data"]
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"✅ გვერდი წარმატებით ჩაიტვირთა",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🏆 გუნდი: {team_data['name']}",
            "team_name": team_data['name'],
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🔤 მოკლე კოდი: {team_data['short_code'] or 'არ მოიძებნა'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🏟️ სტადიონი: {team_data['stadium'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🏙️ ქალაქი: {team_data['city'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🌍 ქვეყანა: {team_data['country'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"👔 მწვრთნელი: {team_data['coach'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🖼️ ლოგო: {'მოიძებნა' if team_data['logo_url'] else 'არ მოიძებნა'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        await asyncio.sleep(1)
        
        # STEP 2: Controller Bot მუშაობს
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": "🔍 ვიწყებ მონაცემების შემოწმებას...",
            "step": 2,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(1)
        
        # Validation
        is_valid, validation_errors = controller.validate_team(team_data)
        
        if not is_valid:
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"❌ ვალიდაცია ვერ გაიარა:",
                "step": 2,
                "status": "error"
            }) + "\n\n"
            for error in validation_errors:
                yield "data: " + json.dumps({
                    "agent": "Controller", 
                    "message": f"   ⚠️ {error}",
                    "step": 2,
                    "status": "error"
                }) + "\n\n"
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"🚫 მონაცემები არ ჩაიწერა ბაზაში",
                "step": 3,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"✅ ვალიდაცია წარმატებით გაიარა",
            "step": 2,
            "status": "completed"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        # Duplicate check
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"🔎 ვამოწმებ თუ უკვე არსებობს ბაზაში...",
            "step": 2,
            "status": "active"
        }) + "\n\n"
        
        is_duplicate, duplicate_msg = await controller.check_duplicate(team_data)
        
        if is_duplicate:
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"⚠️ {duplicate_msg}",
                "step": 2,
                "status": "error"
            }) + "\n\n"
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"🚫 გუნდი უკვე არსებობს ბაზაში",
                "step": 3,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"✅ გუნდი არ არის ბაზაში",
            "step": 2,
            "status": "completed"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        # STEP 3: Save to database
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"💾 ვინახავ მონაცემებს ბაზაში...",
            "step": 3,
            "status": "active"
        }) + "\n\n"
        
        save_success, save_msg = await controller.save_team(team_data)
        
        if not save_success:
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"❌ {save_msg}",
                "step": 3,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"✅ {save_msg}",
            "step": 3,
            "status": "completed",
            "done": True
        }) + "\n\n"
    
    return StreamingResponse(agent_runner(), media_type="text/event-stream")ate().toLocaleTimeString('ka-GE');
                
                log.innerHTML = `
                    <span class="text-gray-600">[${timestamp}]</span>
                    <strong class="${agentColors[agent] || 'text-gray-400'}">[${agent}]</strong>
                    <span class="${colors[type]}">${message}</span>
                `;

                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// ლოგები გასუფთავდა</div>';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)