"""
Fara-7B CUA Demo - Streamlit Frontend
A Computer Use Agent demo application powered by Microsoft Fara-7B

Usage:
    streamlit run app.py --server.address 0.0.0.0 --server.port 8501

Configuration:
    Modify SSH_HOST to point to your Azure GPU VM running VLLM server.
"""

import streamlit as st
import subprocess
import threading
import queue
import time
import os
import base64
from pathlib import Path
import re
from datetime import datetime

# ============================================================================
# CONFIGURATION - Modify these settings for your environment
# ============================================================================
SSH_HOST = "root@YOUR_VM_IP"  # Replace with your Azure GPU VM IP
SSH_OPTIONS = "-o StrictHostKeyChecking=no"
REMOTE_FARA_PATH = "/root/fara"
REMOTE_PYTHON = "/root/fara/.venv/bin/python"
REMOTE_SCREENSHOTS_PATH = "/root/fara/streamlit_screenshots"

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
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


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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


def run_fara_task(task, start_page, max_rounds, output_queue):
    """Run Fara task in background thread"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = f"{REMOTE_SCREENSHOTS_PATH}/{timestamp}"
    
    # Prepare and run command
    setup_cmd = (
        f"pkill -9 Xvfb 2>/dev/null; pkill -9 firefox 2>/dev/null; sleep 1; "
        f"export DISPLAY=:99; Xvfb :99 -screen 0 1920x1080x24 &>/dev/null & sleep 2; "
        f"mkdir -p {screenshot_dir}"
    )
    
    fara_cmd = (
        f"{REMOTE_PYTHON} -m fara.run_fara "
        f"--task '{task}' "
        f"--start_page '{start_page}' "
        f"--max_rounds {max_rounds} "
        f"--save_screenshots "
        f"--downloads_folder {screenshot_dir}"
    )
    
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


def get_remote_screenshots(remote_dir):
    """Get list of screenshots from remote directory"""
    command = f"ls -1 {remote_dir}/*.png 2>/dev/null | sort"
    output, code = run_ssh_command(command, timeout=10)
    if code == 0 and output.strip():
        return [f.strip() for f in output.strip().split('\n') if f.strip()]
    return []


def download_screenshot(remote_path, local_path):
    """Download a screenshot from remote server"""
    command = f'scp {SSH_OPTIONS} {SSH_HOST}:{remote_path} "{local_path}"'
    try:
        subprocess.run(command, shell=True, capture_output=True, timeout=30)
        return os.path.exists(local_path)
    except:
        return False


def image_to_base64(image_path):
    """Convert image to base64 for display"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def display_clickable_image(image_path, caption="", key=None):
    """Display an image that can be clicked to enlarge"""
    if os.path.exists(image_path):
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
    
    for line in lines:
        # Match Thought
        thought_match = re.search(r'Thought #(\d+):\s*(.*)', line)
        if thought_match:
            thoughts.append({
                'num': thought_match.group(1),
                'text': thought_match.group(2)
            })
        
        # Match Action
        action_match = re.search(
            r"Action #(\d+):\s*executing tool '(\w+)'.*arguments\s*(\{.*\})",
            line
        )
        if action_match:
            actions.append({
                'num': action_match.group(1),
                'tool': action_match.group(2),
                'args': action_match.group(3)
            })
        
        # Match Observation
        obs_match = re.search(r'Observation#(\d+):\s*(.*)', line)
        if obs_match:
            observations.append({
                'num': obs_match.group(1),
                'text': obs_match.group(2)
            })
        
        # Match Final Answer
        if 'Final Answer:' in line:
            final_answer = line.split('Final Answer:')[1].strip()
    
    return thoughts, actions, observations, final_answer


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("## 🖥️ Azure GPU VM")
    st.markdown("---")
    st.markdown("## 🔧 System Status")
    
    # GPU Stats refresh button
    if st.button("🔄 Refresh Status"):
        st.rerun()
    
    # Check VLLM status
    vllm_status = check_vllm_status()
    if vllm_status:
        st.success("✅ VLLM Server: Running")
    else:
        st.error("❌ VLLM Server: Not Running")
    
    # GPU Stats
    st.markdown("### 📊 GPU Metrics")
    gpu_stats = get_gpu_stats()
    if gpu_stats:
        gpu_util = gpu_stats['gpu_util']
        mem_used = gpu_stats['mem_used']
        mem_total = gpu_stats['mem_total']
        mem_pct = int(mem_used / mem_total * 100) if mem_total > 0 else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🎮 GPU Utilization", f"{gpu_util}%")
            st.metric("🌡️ Temperature", f"{gpu_stats['temperature']}°C")
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


# ============================================================================
# MAIN CONTENT
# ============================================================================

st.markdown(
    '<p class="main-header">🤖 Fara-7B Computer Use Agent</p>',
    unsafe_allow_html=True
)
st.markdown(
    '<p class="sub-header">Autonomous web browsing powered by Microsoft\'s Fara-7B model</p>',
    unsafe_allow_html=True
)

# Example tasks
st.markdown("### 📝 Example Tasks")
example_tasks = {
    "🚗 Tesla Model Y Price": {
        "task": "Search for Tesla Model Y price and record the starting price in US market",
        "start_page": "https://www.tesla.com/"
    },
    "☁️ Azure VM Pricing": {
        "task": "Find the hourly price for NC A100 v4 series virtual machine",
        "start_page": "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/"
    },
    "🏠 Beijing Housing Portal": {
        "task": "Navigate to the existing house online signing system and find the login entrance",
        "start_page": "https://zjw.beijing.gov.cn/"
    },
    "📝 Form Filling Demo": {
        "task": "Fill the test form: First Name=John, Last Name=Doe, then click Submit",
        "start_page": "https://www.w3schools.com/html/html_forms.asp"
    },
    "🔍 GitHub Repo Info": {
        "task": "Search for microsoft/Fara on GitHub, find the Star count and report it",
        "start_page": "https://github.com/"
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
    max_rounds = st.slider("Max Rounds", min_value=5, max_value=30, value=12)

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
                
                # Update output display
                with output_placeholder:
                    thoughts, actions, observations, final = parse_fara_output(full_output)
                    
                    display_html = ""
                    for i, t in enumerate(thoughts):
                        display_html += f'<div class="thought-box">💭 <b>Thought #{t["num"]}</b>: {t["text"]}</div>'
                        if i < len(actions):
                            a = actions[i]
                            display_html += f'<div class="action-box">🎯 <b>Action #{a["num"]}</b>: {a["tool"]}</div>'
                        if i < len(observations):
                            o = observations[i]
                            display_html += f'<div class="observation-box">👁️ <b>Observation #{o["num"]}</b>: {o["text"][:100]}...</div>'
                    
                    st.markdown(display_html, unsafe_allow_html=True)
                    
                    if final:
                        st.session_state.final_answer = final
                
                # Update screenshots
                if screenshot_dir:
                    screenshots = get_remote_screenshots(screenshot_dir)
                    if screenshots:
                        with screenshot_placeholder:
                            latest = screenshots[-1]
                            local_temp = f"temp_screenshot_{len(screenshots)}.png"
                            if download_screenshot(latest, local_temp):
                                st.image(
                                    local_temp,
                                    caption=f"Step {len(screenshots)}",
                                    use_container_width=True
                                )
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
            if not thread.is_alive():
                break
            continue
    
    # Show final answer
    if st.session_state.final_answer:
        with final_answer_container:
            st.markdown("### 🎯 Final Answer")
            st.markdown(
                f'<div class="final-answer">{st.session_state.final_answer}</div>',
                unsafe_allow_html=True
            )
    
    # Show all screenshots with tabs
    if screenshot_dir:
        st.markdown("### 📸 Screenshot Gallery")
        screenshots = get_remote_screenshots(screenshot_dir)
        if screenshots:
            local_screenshots = []
            for i, ss in enumerate(screenshots):
                local_temp = f"temp_ss_{i}.png"
                if download_screenshot(ss, local_temp):
                    local_screenshots.append((i, local_temp))
            
            if local_screenshots:
                tab_names = [f"Step {i+1}" for i, _ in local_screenshots]
                tabs = st.tabs(tab_names)
                
                for tab_idx, (i, local_path) in enumerate(local_screenshots):
                    with tabs[tab_idx]:
                        st.image(
                            local_path,
                            caption=f"Screenshot Step {i+1}",
                            use_container_width=True
                        )
                        with open(local_path, "rb") as f:
                            st.download_button(
                                label=f"📥 Download Step {i+1}",
                                data=f.read(),
                                file_name=f"fara_step_{i+1}.png",
                                mime="image/png"
                            )
                
                # Cleanup temp files
                for _, local_path in local_screenshots:
                    try:
                        os.remove(local_path)
                    except:
                        pass
    
    st.success("✅ Task completed!")

# GPU monitoring when idle
if not st.session_state.running:
    st.markdown("---")
    st.markdown("### 📈 Real-time GPU Monitoring")
    
    gpu_chart_placeholder = st.empty()
    
    with gpu_chart_placeholder:
        gpu_stats = get_gpu_stats()
        if gpu_stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🎮 GPU Utilization", f"{gpu_stats['gpu_util']}%")
            with col2:
                st.metric("💾 VRAM Used", f"{gpu_stats['mem_used']} MB")
            with col3:
                st.metric("📊 VRAM Total", f"{gpu_stats['mem_total']} MB")
            with col4:
                st.metric("🌡️ Temperature", f"{gpu_stats['temperature']}°C")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888;">
    <p>Powered by <b>Microsoft Fara-7B</b> | Built with Streamlit</p>
    <p>Model: 7B Parameters | License: MIT | GPU: Azure H100/A100</p>
</div>
""", unsafe_allow_html=True)
