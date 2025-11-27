"""
Fara-7B CUA Demo - Streamlit Frontend
A Computer Use Agent demo application powered by Microsoft Fara-7B

This application automatically manages the VLLM backend:
- On startup, checks if VLLM server is running
- If not running, starts VLLM and waits for it to be ready
- Only then displays the main UI
"""

import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="Fara-7B Computer Use Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

import subprocess
import threading
import queue
import time
import os
import base64
from pathlib import Path
import re
from datetime import datetime

# Configuration
SSH_HOST = "root@4.218.23.43"
SSH_OPTIONS = "-o StrictHostKeyChecking=no"
REMOTE_FARA_PATH = "/root/fara"
REMOTE_PYTHON = "/root/fara/.venv/bin/python"
REMOTE_SCREENSHOTS_PATH = "/root/fara/streamlit_screenshots"

# VLLM Configuration
VLLM_PORT = 5000
VLLM_MODEL_PATH = "/root/fara/model_checkpoints/fara-7b"
VLLM_MODEL_NAME = "microsoft/Fara-7B"


# =============================================================================
# Backend Management Functions (run before UI)
# =============================================================================

def run_ssh_command_simple(command, timeout=30):
    """Execute SSH command and return output (simplified version for startup)"""
    full_command = f'ssh {SSH_OPTIONS} {SSH_HOST} "{command}"'
    try:
        result = subprocess.run(
            full_command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout + result.stderr, result.returncode
    except Exception as e:
        return str(e), -1


def check_vllm_running():
    """Check if VLLM server is responding"""
    cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{VLLM_PORT}/v1/models"
    output, code = run_ssh_command_simple(cmd, timeout=10)
    return "200" in output


def start_vllm_backend():
    """Start VLLM server on remote machine"""
    # First check if already running
    if check_vllm_running():
        return True, "VLLM already running"
    
    # Start VLLM server
    vllm_cmd = (
        f"cd {REMOTE_FARA_PATH} && source .venv/bin/activate && "
        f"nohup vllm serve {VLLM_MODEL_PATH} "
        f"--port {VLLM_PORT} --dtype auto --max-model-len 32768 "
        f"--gpu-memory-utilization 0.9 "
        f"--served-model-name {VLLM_MODEL_NAME} "
        f"--trust-remote-code > /tmp/vllm.log 2>&1 &"
    )
    run_ssh_command_simple(vllm_cmd, timeout=10)
    
    # Wait for VLLM to be ready (model loading takes time)
    max_wait = 120  # 2 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        if check_vllm_running():
            return True, "VLLM started successfully"
        time.sleep(3)
    
    return False, "VLLM failed to start within timeout"


def ensure_backend_ready():
    """Ensure VLLM backend is ready before showing UI"""
    if 'backend_ready' not in st.session_state:
        st.session_state.backend_ready = False
        st.session_state.backend_message = ""
    
    if st.session_state.backend_ready:
        return True
    
    # Show startup screen
    st.markdown("""
    <style>
        .startup-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 60vh;
        }
        .startup-title {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1E88E5;
            margin-bottom: 1rem;
        }
        .startup-status {
            font-size: 1.2rem;
            color: #666;
        }
    </style>
    <div class="startup-container">
        <p class="startup-title">🤖 Fara-7B Computer Use Agent</p>
    </div>
    """, unsafe_allow_html=True)
    
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    
    # Step 1: Check VLLM status
    status_placeholder.info("🔍 Checking VLLM backend status...")
    progress_bar.progress(10)
    
    if check_vllm_running():
        status_placeholder.success("✅ VLLM backend is already running!")
        progress_bar.progress(100)
        time.sleep(1)
        st.session_state.backend_ready = True
        st.session_state.backend_message = "Backend was already running"
        st.rerun()
        return True
    
    # Step 2: Start VLLM
    status_placeholder.warning("🚀 Starting VLLM server... (this may take 30-60 seconds)")
    progress_bar.progress(20)
    
    # Start VLLM in background
    vllm_cmd = (
        f"cd {REMOTE_FARA_PATH} && source .venv/bin/activate && "
        f"nohup vllm serve {VLLM_MODEL_PATH} "
        f"--port {VLLM_PORT} --dtype auto --max-model-len 32768 "
        f"--gpu-memory-utilization 0.9 "
        f"--served-model-name {VLLM_MODEL_NAME} "
        f"--trust-remote-code > /tmp/vllm.log 2>&1 &"
    )
    run_ssh_command_simple(vllm_cmd, timeout=10)
    
    # Step 3: Wait for VLLM to be ready
    max_wait = 90
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        elapsed = time.time() - start_time
        progress = min(20 + int(elapsed / max_wait * 70), 90)
        progress_bar.progress(progress)
        
        status_placeholder.info(f"⏳ Loading Fara-7B model... ({int(elapsed)}s)")
        
        if check_vllm_running():
            progress_bar.progress(100)
            status_placeholder.success("✅ VLLM backend started successfully!")
            time.sleep(1)
            st.session_state.backend_ready = True
            st.session_state.backend_message = f"Backend started in {int(elapsed)}s"
            st.rerun()
            return True
        
        time.sleep(2)
    
    # Failed to start
    status_placeholder.error("❌ Failed to start VLLM backend. Please check the server.")
    st.stop()
    return False


# =============================================================================
# Run backend check FIRST before any UI
# =============================================================================
# Note: ensure_backend_ready() is called after set_page_config in the UI section


# Custom CSS
st.markdown("""
<style>
    /* Reduce padding between sidebar and main content */
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    
    /* Adjust sidebar width */
    [data-testid="stSidebar"] {
        min-width: 280px !important;
        max-width: 320px !important;
    }
    
    /* Reduce main content left margin */
    .main .block-container {
        padding-top: 2rem;
        padding-left: 2rem !important;
    }
    
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .thought-box {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 4px solid #1976d2;
    }
    .action-box {
        background-color: #e8f5e9;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 4px solid #388e3c;
    }
    .observation-box {
        background-color: #fff3e0;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 4px solid #f57c00;
    }
    .final-answer {
        background-color: #f3e5f5;
        padding: 15px;
        border-radius: 10px;
        border: 2px solid #7b1fa2;
        font-size: 1.1rem;
    }
    .screenshot-container {
        border: 2px solid #ddd;
        border-radius: 10px;
        padding: 10px;
        margin: 10px 0;
    }
    /* Modal for enlarged screenshots */
    .modal-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        z-index: 1000;
        cursor: pointer;
    }
    .modal-content {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        max-width: 90%;
        max-height: 90%;
    }
    .clickable-image {
        cursor: pointer;
        transition: transform 0.2s;
    }
    .clickable-image:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    .gpu-active {
        color: #4caf50;
        font-weight: bold;
    }
    .gpu-idle {
        color: #ff9800;
    }
</style>
""", unsafe_allow_html=True)


def run_ssh_command(command, timeout=300):
    """Execute SSH command and return output"""
    full_command = f'ssh {SSH_OPTIONS} {SSH_HOST} "{command}"'
    try:
        result = subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", -1
    except Exception as e:
        return str(e), -1


def get_gpu_stats():
    """Get GPU utilization from remote server"""
    command = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"
    output, code = run_ssh_command(command, timeout=10)
    if code == 0 and output.strip():
        try:
            parts = output.strip().split(',')
            return {
                'gpu_util': int(parts[0].strip()),
                'mem_used': int(parts[1].strip()),
                'mem_total': int(parts[2].strip()),
                'temperature': int(parts[3].strip())
            }
        except:
            pass
    return None


def check_vllm_status():
    """Check if VLLM server is running"""
    command = "curl -s http://localhost:5000/v1/models 2>/dev/null | head -1"
    output, code = run_ssh_command(command, timeout=10)
    return "models" in output.lower() or "fara" in output.lower()


def start_vllm_server():
    """Start VLLM server if not running"""
    vllm_cmd = (
        "cd /root/fara && source .venv/bin/activate && "
        "nohup vllm serve /root/fara/model_checkpoints/fara-7b "
        "--port 5000 --dtype auto --max-model-len 32768 "
        "--gpu-memory-utilization 0.9 "
        "--served-model-name microsoft/Fara-7B "
        "--trust-remote-code > /tmp/vllm.log 2>&1 &"
    )
    run_ssh_command(vllm_cmd, timeout=30)
    return True


def get_vllm_throughput():
    """Get VLLM throughput from log - find last non-zero value"""
    # Get the last throughput value using simple grep
    # First try to get any non-zero value from recent logs
    command = (
        "grep 'generation throughput' /tmp/vllm.log | tail -10 | "
        "grep -v '0.0 tokens' | tail -1 | "
        "grep -oE 'generation throughput: [0-9.]+' | "
        "cut -d: -f2 | tr -d ' '"
    )
    output, code = run_ssh_command(command, timeout=5)
    if code == 0 and output.strip():
        try:
            val = float(output.strip())
            if val > 0:
                return val
        except Exception:
            pass
    return 0.0


def ensure_vllm_running():
    """Ensure VLLM is running, start if not"""
    if not check_vllm_status():
        st.warning("⏳ VLLM not running, starting server...")
        start_vllm_server()
        # Wait for VLLM to start
        for i in range(60):  # Wait up to 60 seconds
            time.sleep(2)
            if check_vllm_status():
                st.success("✅ VLLM server started successfully!")
                return True
        st.error("❌ Failed to start VLLM server")
        return False
    return True


def run_fara_task(task, start_page, max_rounds, output_queue):
    """Run Fara task in background thread"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = f"{REMOTE_SCREENSHOTS_PATH}/{timestamp}"
    
    # Sanitize task: normalize whitespace and remove problematic characters
    sanitized_task = task.replace('\n', ' ').replace('\r', ' ')
    sanitized_task = ' '.join(sanitized_task.split())  # Normalize whitespace
    # Remove parentheses which cause shell parsing issues
    sanitized_task = sanitized_task.replace('(', '').replace(')', '')
    sanitized_task = sanitized_task.replace('"', '').replace("'", '')
    
    # Ensure URL has protocol prefix
    if start_page and not start_page.startswith(('http://', 'https://')):
        start_page = 'https://' + start_page
    
    # Prepare and run command
    setup_cmd = f"pkill -9 Xvfb 2>/dev/null; pkill -9 firefox 2>/dev/null; sleep 1; " \
                f"export DISPLAY=:99; Xvfb :99 -screen 0 1920x1080x24 &>/dev/null & sleep 2; " \
                f"mkdir -p {screenshot_dir}"
    
    fara_cmd = f"{REMOTE_PYTHON} -m fara.run_fara " \
               f"--task '{sanitized_task}' " \
               f"--start_page '{start_page}' " \
               f"--max_rounds {max_rounds} " \
               f"--save_screenshots " \
               f"--downloads_folder {screenshot_dir}"
    
    full_command = f"cd {REMOTE_FARA_PATH}; {setup_cmd}; {fara_cmd} 2>&1"
    
    try:
        process = subprocess.Popen(
            f'ssh {SSH_OPTIONS} {SSH_HOST} "{full_command}"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_queue.put(('screenshot_dir', screenshot_dir))
        
        for line in iter(process.stdout.readline, ''):
            if line:
                output_queue.put(('output', line))
        
        process.wait()
        output_queue.put(('done', process.returncode))
        
    except Exception as e:
        output_queue.put(('error', str(e)))


def get_remote_screenshots(local_dir):
    """Get list of screenshots from local directory, sorted by number"""
    import glob
    screenshots = glob.glob(f"{local_dir}/*.png")
    # Sort by screenshot number (screenshot0, screenshot1, etc.)
    def get_num(path):
        import re
        match = re.search(r'screenshot(\d+)', path)
        return int(match.group(1)) if match else 0
    return sorted(screenshots, key=get_num)


# =============================================================================
# Human Intervention Functions
# =============================================================================

def check_pause_status():
    """Check if Fara is waiting for human input"""
    command = "cat /tmp/fara_pause_signal 2>/dev/null"
    output, code = run_ssh_command(command, timeout=5)
    if code == 0 and output.strip():
        return True, output.strip()
    return False, None


def send_human_input(user_input):
    """Send human input to Fara agent"""
    # Escape the input for shell
    escaped_input = user_input.replace("'", "'\\''")
    command = f"echo '{escaped_input}' > /tmp/fara_human_input"
    output, code = run_ssh_command(command, timeout=5)
    return code == 0


def clear_pause_status():
    """Clear pause status files"""
    command = "rm -f /tmp/fara_pause_signal /tmp/fara_human_input"
    run_ssh_command(command, timeout=5)


def download_screenshot(src_path, dest_path):
    """Copy screenshot locally (same machine, no SSH needed)"""
    import shutil
    try:
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            return True
        return False
    except:
        return False


def image_to_base64(image_path):
    """Convert image to base64 for display"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def display_clickable_image(image_path, caption="", key=None):
    """Display an image that can be clicked to enlarge"""
    if os.path.exists(image_path):
        img_base64 = image_to_base64(image_path)
        
        # Use expander for enlargeable view
        with st.expander(f"🖼️ {caption} (Click to enlarge)", expanded=False):
            st.image(image_path, use_container_width=True)
        
        # Show thumbnail
        st.image(image_path, caption=caption, use_container_width=True)


def parse_fara_output(output_text):
    """Parse Fara output into structured format"""
    thoughts = []
    actions = []
    observations = []
    final_answer = None
    
    lines = output_text.split('\n')
    current_thought = None
    current_action = None
    
    for line in lines:
        # Match Thought
        thought_match = re.search(r'Thought #(\d+):\s*(.*)', line)
        if thought_match:
            current_thought = {'num': thought_match.group(1), 'text': thought_match.group(2)}
            thoughts.append(current_thought)
        
        # Match Action
        action_match = re.search(r"Action #(\d+):\s*executing tool '(\w+)'.*arguments\s*(\{.*\})", line)
        if action_match:
            current_action = {
                'num': action_match.group(1),
                'tool': action_match.group(2),
                'args': action_match.group(3)
            }
            actions.append(current_action)
        
        # Match Observation
        obs_match = re.search(r'Observation#(\d+):\s*(.*)', line)
        if obs_match:
            observations.append({'num': obs_match.group(1), 'text': obs_match.group(2)})
        
        # Match Final Answer
        if 'Final Answer:' in line:
            final_answer = line.split('Final Answer:')[1].strip()
    
    return thoughts, actions, observations, final_answer


# =============================================================================
# STARTUP: Ensure VLLM backend is ready before showing main UI
# =============================================================================
if not ensure_backend_ready():
    st.stop()


# Sidebar
with st.sidebar:
    st.markdown("## 🖥️ Azure NC40 H100 VM")
    st.markdown("---")
    st.markdown("## 🔧 System Status")
    
    # GPU Stats refresh button
    if st.button("🔄 Refresh Status"):
        st.rerun()
    
    # VLLM is guaranteed running at this point
    st.success("✅ VLLM Server: Running")
    
    # GPU Stats
    st.markdown("### 📊 GPU Metrics")
    gpu_stats = get_gpu_stats()
    if gpu_stats:
        # Show GPU utilization with status indicator
        gpu_util = gpu_stats['gpu_util']
        mem_used = gpu_stats['mem_used']
        mem_total = gpu_stats['mem_total']
        mem_pct = int(mem_used / mem_total * 100) if mem_total > 0 else 0
        
        # Get throughput
        throughput = get_vllm_throughput()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🎮 GPU Utilization", f"{gpu_util}%")
            st.metric("⚡ Throughput", f"{throughput:.1f} tok/s")
        with col2:
            st.metric("💾 VRAM Used", f"{mem_used} MB")
            st.metric("📊 VRAM %", f"{mem_pct}%")
        
        # Progress bars
        st.progress(min(gpu_util / 100, 1.0), text=f"GPU: {gpu_util}%")
        st.progress(min(mem_pct / 100, 1.0), text=f"VRAM: {mem_pct}%")
        
        # Status explanation
        if gpu_util == 0 and mem_used > 50000:
            st.info("💡 Model loaded in VRAM. GPU activates during inference.")
    else:
        st.warning("⚠️ Unable to fetch GPU stats")
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown("""
    **Fara-7B** is Microsoft's first agentic small language model 
    designed for computer use automation.
    
    - 🧠 7B Parameters
    - 📜 MIT License
    - 🖥️ Browser Automation
    - 🌐 Multi-language Support
    """)
    
    # Human Intervention Section
    st.markdown("---")
    st.markdown("### 🛑 Human Intervention")
    
    # Check current pause status
    is_paused, pause_reason = check_pause_status()
    
    if is_paused:
        st.error("⚠️ Agent Paused!")
        st.warning(f"Reason: {pause_reason}")
    else:
        st.info("💡 Agent running. Use below to intervene when needed.")
    
    # Use form to prevent rerun on submit (which would kill the running task)
    with st.form(key="human_intervention_form", clear_on_submit=True):
        human_input = st.text_input(
            "Enter your input:",
            placeholder="e.g., captcha code, verification..."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit_btn = st.form_submit_button("✅ Submit", type="primary")
        with col2:
            skip_btn = st.form_submit_button("⏭️ Skip")
        
        if submit_btn:
            if human_input:
                if send_human_input(human_input):
                    st.success(f"✅ Sent: {human_input}")
                else:
                    st.error("Failed to send")
            else:
                st.warning("Please enter input first")
        
        if skip_btn:
            if send_human_input("SKIP"):
                st.info("Skipped")

# Main content
st.markdown('<p class="main-header">🤖 Fara-7B Computer Use Agent</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Autonomous web browsing powered by Microsoft\'s Fara-7B model</p>', unsafe_allow_html=True)

# Example tasks
st.markdown("### 📝 Example Tasks")
example_tasks = {
    "🏠 Anjuke Beijing Homes": {
        "task": "Find the property listing on the current page, record the price and area of the first property",
        "start_page": "https://beijing.anjuke.com/sale/"
    },
    "🏡 Anjuke Shanghai Rentals": {
        "task": "Find the rental listing on the current page, record the monthly rent of the first property",
        "start_page": "https://shanghai.anjuke.com/rent/"
    },
    "🔍 GitHub Fara Repo": {
        "task": "Search for microsoft Fara, enter the repository page, find and record the Star count",
        "start_page": "https://github.com/"
    },
    "📰 Hacker News Top Story": {
        "task": "Find the top story on the current page, record its title and points",
        "start_page": "https://news.ycombinator.com/"
    },
    "📚 Wikipedia Search": {
        "task": "Search for Microsoft, find and record the founding year of the company",
        "start_page": "https://en.wikipedia.org/"
    },
    "🏠 US Housing Info": {
        "task": "Find information about renting vs buying a home, summarize the key points",
        "start_page": "https://www.usa.gov/housing"
    }
}

# Task selection
col1, col2 = st.columns([1, 2])
with col1:
    selected_example = st.selectbox(
        "Select an example task:",
        ["Custom Task"] + list(example_tasks.keys())
    )

# Task input
if selected_example != "Custom Task":
    default_task = example_tasks[selected_example]["task"]
    default_url = example_tasks[selected_example]["start_page"]
else:
    default_task = ""
    default_url = "https://www.google.com"

with col2:
    # Increase default max_rounds for multi-step tasks
    max_rounds = st.slider("Max Rounds", min_value=5, max_value=50, value=20)

task_input = st.text_area(
    "Task Description:",
    value=default_task,
    height=100,
    placeholder="Describe what you want the agent to do..."
)

start_page = st.text_input(
    "Start Page URL:",
    value=default_url
)

# Run button
col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    run_button = st.button("▶️ Run Task", type="primary", use_container_width=True)
with col2:
    stop_button = st.button("⏹️ Stop", use_container_width=True)

# Output area
st.markdown("---")
st.markdown("### 🖥️ Execution Output")

# Initialize session state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'output_lines' not in st.session_state:
    st.session_state.output_lines = []
if 'screenshot_dir' not in st.session_state:
    st.session_state.screenshot_dir = None
if 'final_answer' not in st.session_state:
    st.session_state.final_answer = None
if 'paused_for_human' not in st.session_state:
    st.session_state.paused_for_human = False
if 'pause_reason' not in st.session_state:
    st.session_state.pause_reason = None
if 'human_input_sent' not in st.session_state:
    st.session_state.human_input_sent = False

# Create layout for output and screenshots
output_col, screenshot_col = st.columns([1, 1])

with output_col:
    output_container = st.container()
    with output_container:
        st.markdown("#### 📜 Agent Reasoning")
        output_placeholder = st.empty()

with screenshot_col:
    screenshot_container = st.container()
    with screenshot_container:
        st.markdown("#### 📸 Screenshots")
        screenshot_placeholder = st.empty()

# Final answer container
final_answer_container = st.container()

if run_button and task_input and start_page:
    st.session_state.running = True
    st.session_state.output_lines = []
    st.session_state.final_answer = None
    
    output_queue = queue.Queue()
    
    # Start background thread
    thread = threading.Thread(
        target=run_fara_task,
        args=(task_input, start_page, max_rounds, output_queue)
    )
    thread.start()
    
    full_output = ""
    screenshot_dir = None
    
    # Create a placeholder for live updates
    with output_placeholder:
        output_text_area = st.empty()
    
    # Process output
    while True:
        try:
            msg_type, msg_data = output_queue.get(timeout=0.5)
            
            if msg_type == 'screenshot_dir':
                screenshot_dir = msg_data
                st.session_state.screenshot_dir = screenshot_dir
            
            elif msg_type == 'output':
                full_output += msg_data
                st.session_state.output_lines.append(msg_data)
                
                # Check for pause signal in output
                if 'PAUSE_FOR_HUMAN' in msg_data or 'pause' in msg_data.lower() and 'waiting' in msg_data.lower():
                    st.session_state.paused_for_human = True
                    # Extract pause reason if available
                    if 'PAUSE_FOR_HUMAN:' in msg_data:
                        reason = msg_data.split('PAUSE_FOR_HUMAN:')[1].strip()
                        st.session_state.pause_reason = reason
                
                # Update output display
                with output_placeholder:
                    # Parse and display structured output
                    thoughts, actions, observations, final = parse_fara_output(full_output)
                    
                    display_html = ""
                    for i, t in enumerate(thoughts):
                        display_html += f'<div class="thought-box">💭 <b>Thought #{t["num"]}</b>: {t["text"]}</div>'
                        if i < len(actions):
                            a = actions[i]
                            display_html += f'<div class="action-box">🎯 <b>Action #{a["num"]}</b>: {a["tool"]}</div>'
                        if i < len(observations):
                            o = observations[i]
                            display_html += f'<div class="observation-box">👁️ <b>Observation #{o["num"]}</b>: {o["text"]}</div>'
                    
                    st.markdown(display_html, unsafe_allow_html=True)
                    
                    # Show human intervention UI if paused
                    if st.session_state.paused_for_human and not st.session_state.human_input_sent:
                        st.warning(f"🛑 Agent Paused: {st.session_state.pause_reason or 'Waiting for human input'}")
                        st.info("The agent needs your help. Please provide input below.")
                    
                    if final:
                        st.session_state.final_answer = final
                
                # Update screenshots
                if screenshot_dir:
                    screenshots = get_remote_screenshots(screenshot_dir)
                    if screenshots:
                        # Show latest screenshot
                        # screenshot0=Initial, screenshot1=After Action #1, etc.
                        latest = screenshots[-1]
                        ss_num = len(screenshots) - 1  # 0-based index
                        local_temp = f"temp_screenshot_{ss_num}.png"
                        if download_screenshot(latest, local_temp):
                            if ss_num == 0:
                                caption = "Initial Page"
                            else:
                                caption = f"After Action #{ss_num}"
                            # Use placeholder.image() directly to update
                            screenshot_placeholder.image(local_temp, caption=caption, use_container_width=True)
                            try:
                                os.remove(local_temp)
                            except:
                                pass
            
            elif msg_type == 'done':
                st.session_state.running = False
                break
            
            elif msg_type == 'error':
                st.error(f"Error: {msg_data}")
                st.session_state.running = False
                break
                
        except queue.Empty:
            # Check if paused for human input
            is_paused, pause_reason = check_pause_status()
            if is_paused:
                st.session_state.paused_for_human = True
                st.session_state.pause_reason = pause_reason
            
            if not thread.is_alive():
                break
            continue
    
    # Reset human intervention state after task completes
    st.session_state.paused_for_human = False
    st.session_state.human_input_sent = False
    clear_pause_status()
    
    # Show final answer
    if st.session_state.final_answer:
        with final_answer_container:
            st.markdown("### 🎯 Final Answer")
            st.markdown(f'<div class="final-answer">{st.session_state.final_answer}</div>', unsafe_allow_html=True)
    
    # Show all screenshots with lightbox
    # Use session_state as fallback for screenshot_dir
    final_screenshot_dir = screenshot_dir if screenshot_dir else st.session_state.screenshot_dir
    if final_screenshot_dir:
        st.markdown("### 📸 Screenshot Gallery (Click to Enlarge)")
        screenshots = get_remote_screenshots(final_screenshot_dir)
        if screenshots:
            # Download all screenshots first
            local_screenshots = []
            for i, ss in enumerate(screenshots):
                local_temp = f"temp_ss_{i}.png"
                if download_screenshot(ss, local_temp):
                    local_screenshots.append((i, local_temp))
            
            # Create tabs for each screenshot
            # screenshot0=Initial Page, screenshot1=After Action #1, etc.
            if local_screenshots:
                tab_names = []
                for i, _ in local_screenshots:
                    if i == 0:
                        tab_names.append("Initial")
                    else:
                        tab_names.append(f"Action #{i}")
                tabs = st.tabs(tab_names)
                
                for tab_idx, (i, local_path) in enumerate(local_screenshots):
                    with tabs[tab_idx]:
                        if i == 0:
                            caption = "Initial Page (before any action)"
                            label = "📥 Download Initial"
                            filename = "fara_initial.png"
                        else:
                            caption = f"After Action #{i}"
                            label = f"📥 Download Action #{i}"
                            filename = f"fara_action_{i}.png"
                        st.image(local_path, caption=caption, use_container_width=True)
                        # Add download button
                        with open(local_path, "rb") as f:
                            st.download_button(
                                label=label,
                                data=f.read(),
                                file_name=filename,
                                mime="image/png"
                            )
                
                # Cleanup temp files
                for _, local_path in local_screenshots:
                    try:
                        os.remove(local_path)
                    except:
                        pass
    
    st.success("✅ Task completed!")

# GPU monitoring auto-refresh (every 5 seconds when idle)
if not st.session_state.running:
    st.markdown("---")
    st.markdown("### 📈 Real-time GPU Monitoring")
    
    gpu_chart_placeholder = st.empty()
    
    # Simple metric display that can be manually refreshed
    with gpu_chart_placeholder:
        gpu_stats = get_gpu_stats()
        if gpu_stats:
            throughput = get_vllm_throughput()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🎮 GPU Utilization", f"{gpu_stats['gpu_util']}%")
            with col2:
                st.metric("💾 VRAM Used", f"{gpu_stats['mem_used']} MB")
            with col3:
                st.metric("📊 VRAM Total", f"{gpu_stats['mem_total']} MB")
            with col4:
                st.metric("⚡ Throughput", f"{throughput:.1f} tok/s")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888;">
    <p>Powered by <b>Microsoft Fara-7B</b> | Built with Streamlit</p>
    <p>Model: 7B Parameters | License: MIT | GPU: Azure NC40 H100 VM</p>
</div>
""", unsafe_allow_html=True)
