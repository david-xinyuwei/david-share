"""
Fara-7B CUA Demo - Streamlit Web UI (Local Version)
Runs directly on H100 GPU VM with local VLLM backend
"""

import streamlit as st
import subprocess
import threading
import queue
import time
import os
import glob
import base64
import re
from pathlib import Path
from datetime import datetime

# Configuration - Local paths for H100 VM
FARA_DIR = "/root/fara"
VENV_PYTHON = "/root/fara/.venv/bin/python"
SCREENSHOTS_DIR = "/root/fara/streamlit_screenshots"
VLLM_PORT = 5000

# Page configuration
st.set_page_config(
    page_title="Fara-7B CUA Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1976d2, #7b1fa2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .gpu-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 5px 0;
    }
    .thought-box {
        background-color: #e3f2fd;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 5px solid #1976d2;
        font-size: 0.95rem;
    }
    .action-box {
        background-color: #e8f5e9;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 5px solid #388e3c;
        font-size: 0.95rem;
    }
    .observation-box {
        background-color: #fff3e0;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        border-left: 4px solid #f57c00;
        font-size: 0.9rem;
    }
    .final-answer {
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
        padding: 20px;
        border-radius: 12px;
        border: 3px solid #7b1fa2;
        font-size: 1.2rem;
        margin: 20px 0;
    }
    .status-running {
        background-color: #fff9c4;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #fbc02d;
    }
    .status-success {
        background-color: #c8e6c9;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #4caf50;
    }
    .example-card {
        background-color: #f5f5f5;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        cursor: pointer;
        transition: all 0.3s;
    }
    .example-card:hover {
        background-color: #e3f2fd;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# Example tasks with icons
EXAMPLE_TASKS = {
    "🚗 Tesla Model Y Price": {
        "task": "Search for Tesla Model Y price and record the starting price in US market",
        "start_page": "https://www.tesla.com/",
        "max_rounds": 12
    },
    "☁️ Azure VM Pricing": {
        "task": "Find the hourly price for NC A100 v4 series virtual machine",
        "start_page": "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/",
        "max_rounds": 10
    },
    "🏠 Beijing Housing Portal": {
        "task": "Navigate to the existing house online signing system and find the personal user login entrance",
        "start_page": "https://zjw.beijing.gov.cn/",
        "max_rounds": 10
    },
    "📝 Form Filling Demo": {
        "task": "Fill the form: First Name=David, Last Name=Wang, Email=test@example.com, then click Submit",
        "start_page": "https://www.w3schools.com/html/html_forms.asp",
        "max_rounds": 10
    },
    "🔍 GitHub Repo Search": {
        "task": "Search for microsoft/Fara on GitHub, find the Star count and latest release version, report these information",
        "start_page": "https://github.com/",
        "max_rounds": 12
    }
}


def get_gpu_stats():
    """Get GPU utilization using nvidia-smi (local)"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "gpu_util": int(parts[0]),
                "mem_used": int(parts[1]),
                "mem_total": int(parts[2]),
                "temperature": int(parts[3]),
                "gpu_name": parts[4] if len(parts) > 4 else "Unknown"
            }
    except Exception as e:
        pass
    return None


def check_vllm_status():
    """Check if VLLM server is running locally"""
    try:
        result = subprocess.run(
            ["curl", "-s", f"http://localhost:{VLLM_PORT}/v1/models"],
            capture_output=True, text=True, timeout=5
        )
        return "fara" in result.stdout.lower() or "models" in result.stdout.lower()
    except:
        return False


def start_vllm_server():
    """Start VLLM server if not running"""
    cmd = f"""
    cd {FARA_DIR} && source .venv/bin/activate && \
    nohup vllm serve 'microsoft/Fara-7B' \
        --port {VLLM_PORT} \
        --dtype auto \
        --max-model-len 8192 \
        > /tmp/vllm.log 2>&1 &
    """
    subprocess.Popen(cmd, shell=True, executable='/bin/bash')
    return True


def run_fara_task(task, start_page, max_rounds, output_queue):
    """Run Fara task locally in background thread"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = f"{SCREENSHOTS_DIR}/{timestamp}"
    
    # Clean up and prepare
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # Kill any existing Xvfb/firefox
    subprocess.run("pkill -9 Xvfb 2>/dev/null", shell=True)
    subprocess.run("pkill -9 firefox 2>/dev/null", shell=True)
    time.sleep(1)
    
    # Start Xvfb
    os.environ["DISPLAY"] = ":99"
    subprocess.Popen(
        "Xvfb :99 -screen 0 1920x1080x24 &>/dev/null &",
        shell=True, executable='/bin/bash'
    )
    time.sleep(2)
    
    # Build Fara command
    cmd = [
        VENV_PYTHON, "-m", "fara.run_fara",
        "--task", task,
        "--start_page", start_page,
        "--max_rounds", str(max_rounds),
        "--save_screenshots",
        "--downloads_folder", screenshot_dir
    ]
    
    output_queue.put(('screenshot_dir', screenshot_dir))
    output_queue.put(('status', 'Starting browser...'))
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=FARA_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "DISPLAY": ":99"}
        )
        
        for line in iter(process.stdout.readline, ''):
            if line:
                output_queue.put(('output', line))
                
                # Also check for new screenshots
                screenshots = sorted(glob.glob(f"{screenshot_dir}/*.png"))
                if screenshots:
                    output_queue.put(('screenshot', screenshots[-1]))
        
        process.wait()
        output_queue.put(('done', process.returncode))
        
    except Exception as e:
        output_queue.put(('error', str(e)))


def get_base64_image(image_path):
    """Convert image to base64 for display"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None


def parse_fara_output(output_text):
    """Parse Fara output into structured format"""
    thoughts = []
    actions = []
    observations = []
    final_answer = None
    
    # Use regex to extract components
    thought_pattern = r'Thought #(\d+):\s*(.*?)(?=Action #|$)'
    action_pattern = r"Action #(\d+):\s*executing tool '(\w+)'"
    obs_pattern = r'Observation#(\d+):\s*(.*?)(?=Thought #|$)'
    
    for match in re.finditer(thought_pattern, output_text, re.DOTALL):
        thoughts.append({'num': match.group(1), 'text': match.group(2).strip()[:200]})
    
    for match in re.finditer(action_pattern, output_text):
        actions.append({'num': match.group(1), 'tool': match.group(2)})
    
    for match in re.finditer(obs_pattern, output_text, re.DOTALL):
        observations.append({'num': match.group(1), 'text': match.group(2).strip()[:100]})
    
    if 'Final Answer:' in output_text:
        final_answer = output_text.split('Final Answer:')[-1].strip().split('\n')[0]
    
    return thoughts, actions, observations, final_answer


# ============== SIDEBAR ==============
with st.sidebar:
    st.markdown("## 🖥️ System Status")
    
    # Refresh button
    if st.button("🔄 Refresh Status", use_container_width=True):
        st.rerun()
    
    st.divider()
    
    # VLLM Status
    vllm_running = check_vllm_status()
    if vllm_running:
        st.success("✅ VLLM Server: Running")
    else:
        st.error("❌ VLLM Server: Not Running")
        if st.button("▶️ Start VLLM Server"):
            start_vllm_server()
            st.info("Starting VLLM... Please wait 60s and refresh")
    
    st.divider()
    
    # GPU Metrics
    st.markdown("### 📊 GPU Metrics")
    gpu_stats = get_gpu_stats()
    
    if gpu_stats:
        st.markdown(f"**{gpu_stats['gpu_name']}**")
        
        # GPU Utilization
        st.metric("🎮 GPU Utilization", f"{gpu_stats['gpu_util']}%")
        st.progress(gpu_stats['gpu_util'] / 100)
        
        # Memory
        mem_pct = int(gpu_stats['mem_used'] / gpu_stats['mem_total'] * 100)
        st.metric("💾 VRAM Usage", f"{gpu_stats['mem_used']} / {gpu_stats['mem_total']} MB")
        st.progress(mem_pct / 100)
        
        # Temperature
        temp_color = "🟢" if gpu_stats['temperature'] < 70 else "🟡" if gpu_stats['temperature'] < 80 else "🔴"
        st.metric("🌡️ Temperature", f"{temp_color} {gpu_stats['temperature']}°C")
    else:
        st.warning("⚠️ GPU stats unavailable")
    
    st.divider()
    
    # Model Info
    st.markdown("### ℹ️ Model Info")
    st.markdown("""
    - **Model**: Fara-7B
    - **Parameters**: 7 Billion
    - **License**: MIT
    - **Base**: Qwen2.5-VL-7B
    - **Capability**: Computer Use Agent
    """)


# ============== MAIN CONTENT ==============
st.markdown('<p class="main-header">🤖 Fara-7B Computer Use Agent</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Microsoft\'s First Agentic Small Language Model for Autonomous Web Browsing</p>', unsafe_allow_html=True)

# Task Selection
st.markdown("### 📋 Select or Create Task")

col1, col2 = st.columns([1, 2])

with col1:
    selected_example = st.selectbox(
        "Example Tasks:",
        ["✏️ Custom Task"] + list(EXAMPLE_TASKS.keys()),
        index=0
    )

with col2:
    if selected_example != "✏️ Custom Task":
        example = EXAMPLE_TASKS[selected_example]
        max_rounds = st.slider("Max Steps", 5, 25, example["max_rounds"])
    else:
        max_rounds = st.slider("Max Steps", 5, 25, 12)

# Task Input
if selected_example != "✏️ Custom Task":
    example = EXAMPLE_TASKS[selected_example]
    task_input = st.text_area(
        "Task Description:",
        value=example["task"],
        height=80
    )
    start_page = st.text_input("Start URL:", value=example["start_page"])
else:
    task_input = st.text_area(
        "Task Description:",
        placeholder="Describe what you want the agent to do...",
        height=80
    )
    start_page = st.text_input("Start URL:", placeholder="https://example.com")

# Control Buttons
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    run_button = st.button("🚀 Run Task", type="primary", use_container_width=True)
with col2:
    clear_button = st.button("🗑️ Clear", use_container_width=True)

st.divider()

# ============== EXECUTION AREA ==============
if run_button:
    if not task_input or not start_page:
        st.error("❌ Please enter both task description and start URL")
    elif not vllm_running:
        st.error("❌ VLLM server is not running. Please start it first from the sidebar.")
    else:
        st.markdown("### 🔄 Execution Progress")
        
        # Status and progress
        status_placeholder = st.empty()
        progress_bar = st.progress(0, text="Starting...")
        
        # Two columns: Output | Screenshot
        col_output, col_screenshot = st.columns([1, 1])
        
        with col_output:
            st.markdown("#### 📝 Agent Reasoning")
            output_container = st.container(height=450)
        
        with col_screenshot:
            st.markdown("#### 📸 Live Browser View")
            screenshot_placeholder = st.empty()
        
        # Result placeholder
        result_placeholder = st.empty()
        
        # Start background task
        output_queue = queue.Queue()
        task_thread = threading.Thread(
            target=run_fara_task,
            args=(task_input, start_page, max_rounds, output_queue)
        )
        task_thread.start()
        
        status_placeholder.info("🔄 Initializing browser and starting task...")
        
        # Process output in real-time
        full_output = ""
        step_count = 0
        screenshot_dir = None
        last_screenshot = None
        
        while True:
            try:
                msg_type, msg_data = output_queue.get(timeout=0.3)
                
                if msg_type == 'screenshot_dir':
                    screenshot_dir = msg_data
                
                elif msg_type == 'status':
                    status_placeholder.info(f"🔄 {msg_data}")
                
                elif msg_type == 'output':
                    full_output += msg_data
                    
                    # Count steps
                    if "Thought #" in msg_data:
                        step_count += 1
                        progress_pct = min(step_count / max_rounds, 0.95)
                        progress_bar.progress(progress_pct, text=f"Step {step_count}/{max_rounds}")
                    
                    # Parse and display
                    thoughts, actions, observations, final = parse_fara_output(full_output)
                    
                    with output_container:
                        for i, t in enumerate(thoughts):
                            st.markdown(f'<div class="thought-box">💭 <b>Thought #{t["num"]}</b>: {t["text"]}</div>', 
                                       unsafe_allow_html=True)
                            if i < len(actions):
                                a = actions[i]
                                st.markdown(f'<div class="action-box">⚡ <b>Action #{a["num"]}</b>: {a["tool"]}</div>', 
                                           unsafe_allow_html=True)
                
                elif msg_type == 'screenshot':
                    if msg_data != last_screenshot:
                        last_screenshot = msg_data
                        img_b64 = get_base64_image(msg_data)
                        if img_b64:
                            screenshot_placeholder.image(
                                f"data:image/png;base64,{img_b64}",
                                caption=f"Step {step_count}",
                                use_container_width=True
                            )
                
                elif msg_type == 'done':
                    break
                
                elif msg_type == 'error':
                    st.error(f"❌ Error: {msg_data}")
                    break
                    
            except queue.Empty:
                # Update GPU stats while waiting
                if not task_thread.is_alive():
                    break
                continue
        
        task_thread.join()
        
        # Final parsing
        thoughts, actions, observations, final_answer = parse_fara_output(full_output)
        
        progress_bar.progress(1.0, text="Complete!")
        
        # Show result
        if final_answer and final_answer != "<no_answer>":
            status_placeholder.success(f"✅ Task completed successfully in {step_count} steps!")
            result_placeholder.markdown(f"""
            <div class="final-answer">
                <h3>🎯 Final Answer</h3>
                <p>{final_answer}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            status_placeholder.warning(f"⚠️ Task ended after {step_count} steps without definitive answer")
        
        # Show all screenshots gallery
        if screenshot_dir:
            st.markdown("### 📷 Screenshot Gallery")
            screenshots = sorted(glob.glob(f"{screenshot_dir}/*.png"))
            if screenshots:
                num_cols = min(len(screenshots), 5)
                cols = st.columns(num_cols)
                for i, ss in enumerate(screenshots):
                    img_b64 = get_base64_image(ss)
                    if img_b64:
                        with cols[i % num_cols]:
                            st.image(f"data:image/png;base64,{img_b64}", 
                                    caption=f"Step {i}", 
                                    use_container_width=True)

# Clear session
if clear_button:
    st.rerun()

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #888; padding: 20px;">
    <p><b>Fara-7B</b> by Microsoft Research | Running on <b>NVIDIA H100</b> GPU</p>
    <p>Model: 7B Parameters | License: MIT | Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)
