"""
Morning Sweep — Live Dashboard Server (SSE + Smart Refresh)
- Graph API poll every 15s, only triggers GPT-5.4 when data changes
- Browser receives Server-Sent Events for instant updates (no page reload)
- http://localhost:8088
"""
import http.server
import re
import threading
import time
import json
import os
import hashlib
import base64
from urllib.parse import urlparse

PORT = int(os.getenv("PORT", "8088"))
AUTH_USER = os.getenv("DASHBOARD_USER", "admin")
AUTH_PASS = os.getenv("DASHBOARD_PASSWORD", "changeme")
AUTH_REALM = "Morning Sweep"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))
EMAIL_HOURS = int(os.getenv("EMAIL_HOURS", "168"))  # default 7 days
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Global state
current_data = {}
last_hash = ""
analyzing = False
lock = threading.Lock()
MAX_POST_BODY = 1048576  # 1MB

def get_data_hash(emails, chats):
    # Include email subjects + chat last message preview to detect new messages in existing chats
    chat_signals = []
    for c in chats:
        preview = c.get('lastMessagePreview', {})
        if preview:
            chat_signals.append(preview.get('createdDateTime', '') + (preview.get('body', {}).get('content', '')[:50] if preview.get('body') else ''))
        else:
            chat_signals.append(str(c.get('id', '')))
    raw = json.dumps([e.get('subject','') for e in emails] + chat_signals, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()

analyzing = False

from morning_sweep import get_token, fetch_recent_emails, fetch_today_calendar, fetch_recent_chats, fetch_user_profile, fetch_people, analyze_with_gpt54

def run_analysis(emails, calendar, chats, profile, people, now):
    global current_data, analyzing
    try:
        enriched = None
        if os.getenv("USE_DATA_LAYER", "").lower() == "true":
            try:
                from morning_sweep import get_enriched_context
                token = get_token()
                enriched = get_enriched_context(token, hours=EMAIL_HOURS)
            except Exception as e:
                print(f"[{now}] ⚠️ Data layer enrichment failed: {e}")
        result = analyze_with_gpt54(emails, calendar, chats, profile, people, enriched=enriched)
        if result:
            # Attach Foundry IQ insights for dashboard display
            if enriched and enriched.get("foundry_iq_insights"):
                result["foundry_iq_insights"] = enriched["foundry_iq_insights"]
            # Add raw chats data for dashboard display
            result['recent_chats'] = [
                {
                    'topic': c.get('topic') or ', '.join(
                        m.get('displayName', '') 
                        for m in c.get('members', []) 
                        if m.get('displayName', '') != (profile.get('displayName', '') if profile else '')
                    ) or 'Self Chat',
                    'chat_type': c.get('chatType', ''),
                    'messages': [
                        {
                            'from': m.get('from', {}).get('user', {}).get('displayName', '') if m.get('from') else '',
                            'content': re.sub(r'<[^>]+>', '', m.get('body', {}).get('content', '')).strip()[:200] or '[📷 Image]',
                            'time': m.get('createdDateTime', ''),
                        }
                        for m in c.get('recentMessages', [])
                        if m.get('body', {}).get('content', '').strip()
                        and '<systemEventMessage' not in m.get('body', {}).get('content', '')
                    ][:10]
                }
                for c in chats
            ]
            with lock:
                current_data = result
            outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'morning_sweep_output.json')
            with open(outpath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            # Save to CosmosDB if data layer enabled
            if os.getenv("USE_DATA_LAYER", "").lower() == "true":
                try:
                    from morning_sweep import save_to_cosmos
                    save_to_cosmos("default", result)
                except Exception as e:
                    print(f"[{now}] ⚠️ CosmosDB save failed: {e}")
            meta = result.get('_meta', {})
            print(f"[{now}] ✅ Analysis complete ({meta.get('total_tokens',0)} tokens)")
    except Exception as e:
        print(f"[{now}] ❌ Analysis error: {e}")
    finally:
        with lock:
            analyzing = False

def poll_and_analyze():
    global current_data, last_hash, analyzing

    while True:
        try:
            now = time.strftime("%H:%M:%S")
            token = get_token()
            emails = fetch_recent_emails(token, hours=EMAIL_HOURS)
            calendar = fetch_today_calendar(token)
            chats = fetch_recent_chats(token)
            people = fetch_people(token)
            profile = fetch_user_profile(token)

            new_hash = get_data_hash(emails, chats)
            with lock:
                hash_changed = new_hash != last_hash
                is_analyzing = analyzing
            status = '(changed!)' if hash_changed else '(same)'
            if is_analyzing:
                status += ' [analyzing...]'
            print(f"[{now}] Poll: {len(emails)} emails, {len(chats)} chats | hash={new_hash[:8]} {status}")

            if hash_changed and not is_analyzing:
                with lock:
                    last_hash = new_hash
                    analyzing = True
                print(f"[{now}] 🤖 Data changed → GPT-5.4 analysis (async)...")
                t = threading.Thread(target=run_analysis, args=(emails, calendar, chats, profile, people, now), daemon=True)
                t.start()
        except Exception as e:
            print(f"[{now}] ❌ {e}")

        time.sleep(POLL_INTERVAL)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Morning Sweep — Live</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',-apple-system,sans-serif;background:linear-gradient(135deg,#e8f0fe 0%,#f3e8ff 50%,#fce4ec 100%);min-height:100vh;padding:24px}
.container{max-width:1200px;margin:0 auto}
.header{margin-bottom:24px}
.header .date{color:#666;font-size:14px}
.header h1{font-size:32px;font-weight:300;color:#1a1a2e}
.header .live{display:inline-block;background:#27ae60;color:white;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:12px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:rgba(255,255,255,0.85);backdrop-filter:blur(10px);border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,0.06)}
.card h2{font-size:16px;font-weight:600;color:#333;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.full-width{grid-column:1/-1}
.email-item{padding:12px;border-radius:10px;margin-bottom:10px;border-left:4px solid #ccc;background:#fafafa}
.email-item.high{border-left-color:#e74c3c;background:#fef5f5}
.email-item.medium{border-left-color:#f39c12;background:#fffbf0}
.email-item.low{border-left-color:#27ae60;background:#f0faf4}
.email-subject{font-weight:600;font-size:14px;color:#222}
.email-from{font-size:12px;color:#888;margin-top:2px}
.email-action{font-size:13px;color:#555;margin-top:6px;padding:6px 10px;background:rgba(0,0,0,0.03);border-radius:6px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;text-transform:uppercase;margin-left:8px}
.badge.high{background:#e74c3c;color:white}.badge.medium{background:#f39c12;color:white}.badge.low{background:#27ae60;color:white}
.action-item{display:flex;align-items:flex-start;gap:10px;padding:12px;border-radius:10px;margin-bottom:8px;background:#fafafa;cursor:pointer;transition:all 0.2s}
.action-item:hover{background:#f0f0ff}
.action-item.done{opacity:0.4}
.action-item.done .action-task{text-decoration:line-through}
.action-check{width:22px;height:22px;border:2px solid #bbb;border-radius:50%;flex-shrink:0;margin-top:2px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.2s}
.action-check:hover{border-color:#7c4dff;background:#f0e8ff}
.action-check.checked{background:#27ae60;border-color:#27ae60}
.action-check.checked::after{content:'✓';color:white;font-size:13px;font-weight:700}
.pri{font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px}
.pri.P0{background:#e74c3c;color:white}.pri.P1{background:#f39c12;color:white}.pri.P2{background:#3498db;color:white}
.profile-item{display:flex;align-items:center;gap:12px;padding:12px;border-radius:10px;margin-bottom:8px;background:#f8f9ff}
.avatar{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:white;flex-shrink:0}
.profile-name{font-weight:600;font-size:14px;color:#222}
.profile-role{font-size:12px;color:#888}
.profile-style{display:inline-block;font-size:11px;padding:2px 8px;border-radius:8px;background:#e8f0fe;color:#1967d2;margin-top:4px}
.profile-tip{font-size:12px;color:#666;margin-top:4px;font-style:italic}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot.positive{background:#27ae60}.dot.neutral{background:#f39c12}.dot.needs-attention{background:#e74c3c}
.net-summary{font-size:13px;color:#555;line-height:1.6;margin-bottom:12px}
.net-label{font-size:12px;font-weight:600;color:#888;text-transform:uppercase;margin-bottom:6px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.tag{padding:4px 12px;border-radius:16px;font-size:12px}
.tag.inner{background:#e8f5e9;color:#2e7d32}.tag.attn{background:#fce4ec;color:#c62828}
.draft-item{padding:14px;border-radius:10px;margin-bottom:10px;background:#f8f9ff;border:1px solid #e8eaff}
.draft-to{font-size:12px;color:#7c4dff;font-weight:600}
.draft-subject{font-size:14px;font-weight:600;color:#333;margin:4px 0}
.draft-body{font-size:13px;color:#555;line-height:1.5;padding:10px;background:white;border-radius:8px;margin-top:8px}
.draft-tone{font-size:11px;color:#999;margin-top:6px;font-style:italic}
.draft-actions{display:flex;gap:8px;margin-top:10px}
.btn{padding:6px 16px;border-radius:8px;font-size:12px;border:none;cursor:pointer;font-weight:600;transition:all 0.2s}
.btn-primary{background:#7c4dff;color:white}.btn-primary:hover{background:#6a3de8}
.btn-secondary{background:#f0f0f0;color:#555}.btn-secondary:hover{background:#e0e0e0}
.btn-success{background:#27ae60;color:white}
.btn-danger{background:#e74c3c;color:white}
.draft-body[contenteditable]{border:2px solid #7c4dff;outline:none}
.toast{position:fixed;top:20px;right:20px;padding:12px 20px;border-radius:10px;color:white;font-size:14px;font-weight:600;z-index:9999;animation:slideIn 0.3s ease}
@keyframes slideIn{from{transform:translateX(100px);opacity:0}to{transform:translateX(0);opacity:1}}
.modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:9998;display:flex;align-items:center;justify-content:center}
.modal{background:white;border-radius:16px;padding:24px;max-width:500px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.2)}
.modal h3{margin-bottom:12px}
.modal p{font-size:14px;color:#555;margin-bottom:16px}
.modal-actions{display:flex;gap:8px;justify-content:flex-end}
.insight-item{padding:12px;border-radius:10px;background:linear-gradient(135deg,#fff3e0,#fce4ec);margin-bottom:8px}
.footer{text-align:center;margin-top:24px;font-size:12px;color:#aaa}
.footer span{color:#7c4dff;font-weight:600}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="date" id="dateStr"></div>
    <h1 id="greeting">Loading...<span class="live">LIVE</span></h1>
  </div>
  <div class="grid">
    <div class="card"><h2>📧 Priority Emails</h2><div id="emails">Loading...</div></div>
    <div class="card"><h2>✅ To-Do <span id="todoCount" style="font-size:12px;color:#7c4dff;margin-left:auto"></span></h2><div id="actions">Loading...</div></div>
    <div class="card"><h2>👥 Contact Profiles</h2><div id="profiles">Loading...</div></div>
    <div class="card"><h2>🔗 Relationship Network</h2><div id="network">Loading...</div></div>
    <div class="card" id="insightsCard" style="display:none"><h2>🔍 Cross-Source Insights</h2><div id="insights"></div></div>
    <div class="card full-width"><h2>✉️ AI-Drafted Replies</h2><div id="drafts">Loading...</div></div>
  </div>
  <div class="footer">Powered by <span>Microsoft Graph API</span> + <span>Azure OpenAI</span> · M365 Morning Sweep · <span>Auto-refresh every 15s</span></div>
</div>
<script>
const colors=['#7c4dff','#1967d2','#e74c3c','#27ae60','#f39c12','#00bcd4','#e91e63','#ff5722','#795548','#607d8b'];
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function ini(n){return n.split(' ').map(w=>w[0]).join('').substring(0,2).toUpperCase()}
function col(n){let h=0;for(let i=0;i<n.length;i++)h=n.charCodeAt(i)+((h<<5)-h);return colors[Math.abs(h)%colors.length]}

function render(data){
  document.getElementById('dateStr').textContent=new Date().toLocaleDateString('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
  document.getElementById('greeting').innerHTML=(data.greeting||'Good morning')+'<span class="live">LIVE</span>';
  
  let h='';
  (data.priority_emails||[]).forEach(e=>{h+=`<div class="email-item ${esc(e.urgency)}"><div class="email-subject">${esc(e.subject)} <span class="badge ${esc(e.urgency)}">${esc(e.urgency)}</span></div><div class="email-from">From: ${esc(e.from)} ${e.from_email?'&lt;'+esc(e.from_email)+'&gt;':''}</div><div class="email-action">💡 ${esc(e.suggested_action)}</div>${e.source_ref?'<div style="font-size:10px;color:#aaa;margin-top:4px">📎 '+esc(e.source_ref)+'</div>':''}</div>`});
  document.getElementById('emails').innerHTML=h||'No emails';

  h='';const items=data.action_items||[];
  document.getElementById('todoCount').textContent=items.length+' pending';
  items.forEach((a,i)=>{
    const d=a.detail||{};
    const preps=(d.prep_needed||[]).map(p=>'<li>'+p+'</li>').join('');
    const people=(d.related_people||[]).map(p=>p.name+(p.role_in_task?' ('+p.role_in_task+')':'')).join(', ');
    h+=`<div class="action-item" onclick="toggleDetail(event,${i})">
      <div class="action-check" id="chk${i}" onclick="event.stopPropagation();toggleTodo(this.parentElement)"></div>
      <div style="flex:1">
        <div><span class="pri ${a.priority}">${a.priority}</span> <span class="action-task">${a.task}</span></div>
        <div style="font-size:11px;color:#999;margin-top:3px">⏰ ${a.deadline} · 📎 ${a.source_ref||a.source||''}</div>
        <div id="detail${i}" class="action-detail" style="display:none;margin-top:10px;padding:10px;background:#f0f4ff;border-radius:8px;font-size:13px">
          ${d.background?'<div style="margin-bottom:8px"><b>📋 Background:</b> '+d.background+'</div>':''}
          ${preps?'<div style="margin-bottom:8px"><b>📝 Preparation:</b><ul style="margin:4px 0 0 16px">'+preps+'</ul></div>':''}
          ${people?'<div style="margin-bottom:8px"><b>👥 People:</b> '+people+'</div>':''}
          ${d.related_history?'<div style="margin-bottom:8px"><b>📚 History:</b> '+d.related_history+'</div>':''}
          ${d.suggested_approach?'<div><b>💡 Approach:</b> '+d.suggested_approach+'</div>':''}
        </div>
      </div>
    </div>`;
  });
  document.getElementById('actions').innerHTML=h||'All clear!';

  h='';
  (data.contact_profiles||[]).forEach(p=>{const c=col(p.name);h+=`<div class="profile-item"><div class="avatar" style="background:${c}">${ini(p.name)}</div><div style="flex:1"><div class="profile-name">${esc(p.name)} ${p.email?'<span style="font-size:11px;color:#999">'+esc(p.email)+'</span>':''}</div><div class="profile-role">${esc(p.role||'')} · ${esc(p.relationship||'')}</div><span class="profile-style">${esc(p.communication_style||'')}</span><div class="profile-tip">${esc(p.tip||'')}</div></div><div class="dot ${(p.sentiment||'neutral').replace(' ','-')}"></div></div>`});
  document.getElementById('profiles').innerHTML=h||'No profiles';

  const net=data.relationship_network||{};
  h=`<div class="net-summary">${net.summary||''}</div>`;
  if(net.inner_circle&&net.inner_circle.length)h+=`<div class="net-label">Inner Circle</div><div class="tags">${net.inner_circle.map(n=>`<span class="tag inner">${esc(n)}</span>`).join('')}</div>`;
  if(net.attention_needed&&net.attention_needed.length)h+=`<div class="net-label">Needs Attention</div><div class="tags">${net.attention_needed.map(n=>`<span class="tag attn">${esc(n)}</span>`).join('')}</div>`;
  document.getElementById('network').innerHTML=h;

  const cx=data.cross_check_insights||[];
  if(cx.length){document.getElementById('insightsCard').style.display='block';h='';cx.forEach(i=>{h+=`<div class="insight-item"><div style="font-size:13px;color:#333;font-weight:500">🔍 ${esc(i.insight)}</div><div style="font-size:11px;color:#888;margin-top:4px">📎 ${(i.sources||[]).map(esc).join(' · ')}</div></div>`});document.getElementById('insights').innerHTML=h}

  window._drafts=data.draft_replies||[];
  h='';
  window._drafts.forEach((d,i)=>{h+=`<div class="draft-item" id="draft${i}"><div class="draft-to">To: ${esc(d.to)} ${d.to_email?'&lt;'+esc(d.to_email)+'&gt;':''}</div><div class="draft-subject">${esc(d.subject)}</div><div class="draft-body" id="draftBody${i}">${esc(d.draft)}</div><div class="draft-tone">🎨 ${esc(d.tone_note)}</div>${d.source_ref?'<div style="font-size:10px;color:#aaa;margin-top:4px">📎 '+esc(d.source_ref)+'</div>':''}<div class="draft-actions"><button class="btn btn-primary" data-idx="${i}" onclick="confirmSendBtn(this)">✉️ Send</button><button class="btn btn-secondary" onclick="editDraft(${i})">✏️ Edit</button></div></div>`});
  document.getElementById('drafts').innerHTML=h||'No drafts';

  // Cost monitor
  const meta=data._meta||{};
  if(meta.total_tokens){document.querySelector('.footer').innerHTML=`Powered by <span>Microsoft Graph API</span> + <span>Azure OpenAI</span> · M365 Morning Sweep · <span>Last analysis: ${meta.timestamp||''} · ${meta.total_tokens} tokens</span>`}
}

// Initial load
fetch('/api/data').then(r=>r.json()).then(render).catch(()=>{});

function toggleTodo(el){
  el.classList.toggle('done');
  const chk=el.querySelector('.action-check');
  chk.classList.toggle('checked');
  const total=document.querySelectorAll('.action-item').length;
  const done=document.querySelectorAll('.action-item.done').length;
  document.getElementById('todoCount').textContent=(total-done)+' pending';
}

function toggleDetail(e,i){
  if(e.target.classList.contains('action-check'))return;
  const d=document.getElementById('detail'+i);
  d.style.display=d.style.display==='none'?'block':'none';
}

// Poll for updates every 10s
let lastJson='';
setInterval(()=>{
  fetch('/api/data').then(r=>r.text()).then(t=>{
    if(t!==lastJson&&t.length>10){lastJson=t;render(JSON.parse(t));document.title='🔔 Updated! — Morning Sweep'}
  }).catch(()=>{});
},10000);
function editDraft(i){
  const el=document.getElementById('draftBody'+i);
  if(el.contentEditable==='true'){
    el.contentEditable='false';
    el.style.border='';
    showToast('Draft saved','#27ae60');
  } else {
    el.contentEditable='true';
    el.focus();
    showToast('Editing... click Edit again to save','#f39c12');
  }
}

function confirmSendBtn(btn){
  const i=parseInt(btn.dataset.idx);
  const d=window._drafts[i];
  const to=d.to, subject=d.subject;
  const body=document.getElementById('draftBody'+i).innerText;
  const overlay=document.createElement('div');
  overlay.className='modal-overlay';
  overlay.innerHTML=`<div class="modal"><h3>✉️ Confirm Send</h3><p><b>To:</b> ${to}<br><b>Subject:</b> ${subject}<br><br><b>Content:</b><br>${body.substring(0,200)}${body.length>200?'...':''}</p><div class="modal-actions"><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button><button class="btn btn-primary" data-idx="${i}" onclick="doSend(this)">Send Now</button></div></div>`;
  document.body.appendChild(overlay);
}

function doSend(btn){
  const i=parseInt(btn.dataset.idx);
  const d=window._drafts[i];
  const body=document.getElementById('draftBody'+i).innerText;
  btn.textContent='Sending...';
  btn.disabled=true;
  fetch('/api/send-mail',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:d.to_email||d.to,subject:d.subject,body:body})})
  .then(r=>r.json()).then(res=>{
    document.querySelector('.modal-overlay').remove();
    if(res.ok){
      showToast('✅ Email sent to '+d.to,'#27ae60');
      const draft=document.getElementById('draft'+i);
      draft.style.opacity='0.5';
      draft.querySelector('.btn-primary').textContent='✅ Sent';
      draft.querySelector('.btn-primary').disabled=true;
    } else {
      showToast('\u274c Failed: '+res.error,'#e74c3c');
    }
  }).catch(e=>{document.querySelector('.modal-overlay').remove();showToast('\u274c '+e,'#e74c3c');});
}

function showToast(msg,color){
  const t=document.createElement('div');
  t.className='toast';
  t.style.background=color;
  t.textContent=msg;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(),3000);
}
</script>
</body>
</html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def check_auth(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Basic '):
            return False
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            user, pwd = decoded.split(':', 1)
            return user == AUTH_USER and pwd == AUTH_PASS
        except:
            return False

    def require_auth(self):
        if not self.check_auth():
            self.send_response(401)
            self.send_header('WWW-Authenticate', f'Basic realm="{AUTH_REALM}"')
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>401 Unauthorized</h1>')
            return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        # Public endpoints (no auth needed)
        public_paths = {'/api/health', '/api/schema'}
        # All other paths require auth
        if path not in public_paths:
            if not self.require_auth():
                return
        if path == '/' or path == '/dashboard.html' or path == '/morning_sweep_dashboard.html':
            # Serve the standalone HTML dashboard
            dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html')
            if os.path.exists(dashboard_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(dashboard_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
        elif path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with lock:
                self.wfile.write(json.dumps(current_data, ensure_ascii=False, default=str).encode('utf-8'))
        elif path == '/api/schema':
            schema = {
                "description": "Morning Sweep API",
                "endpoints": {
                    "GET /": "Dashboard HTML page (requires Basic Auth)",
                    "GET /api/data": "Current analysis result as JSON (requires Basic Auth)",
                    "GET /api/schema": "This API documentation (public)",
                    "GET /api/health": "Service health check: status, metrics, data freshness (public)",
                    "GET /api/insights": "CosmosDB historical trends (requires Basic Auth)",
                    "POST /api/send-mail": "Send email via Graph API. Body: {to, subject, body, attachments?} (requires Basic Auth)",
                    "POST /api/optimize-draft": "Profile-driven email optimization. Body: {original_draft, subject, to, persona} (requires Basic Auth)",
                    "POST /api/refresh": "Force re-analysis. Body: {hours?} to change time range (requires Basic Auth)"
                },
                "data_schema": {
                    "greeting": "string",
                    "priority_emails": [{"subject":"str","from":"str","from_email":"str","urgency":"high|medium|low","suggested_action":"str","reason":"str","source_ref":"str"}],
                    "action_items": [{"task":"str","source":"str","source_ref":"str","deadline":"str","priority":"P0|P1|P2","detail":{"background":"str","prep_needed":["str"],"related_people":[{"name":"str","role_in_task":"str"}],"related_history":"str","suggested_approach":"str"}}],
                    "cross_check_insights": [{"insight":"str","sources":["str"],"source_ref":"str"}],
                    "contact_profiles": [{"name":"str","email":"str","role":"str","relationship":"str","communication_style":"str","recent_topics":["str"],"interaction_frequency":"str","sentiment":"str","tip":"str"}],
                    "relationship_network": {"summary":"str","inner_circle":["str"],"attention_needed":["str"]},
                    "draft_replies": [{"to":"str","to_email":"str","subject":"str","draft":"str","tone_note":"str","source_ref":"str"}],
                    "_meta": {"prompt_tokens":"int","completion_tokens":"int","total_tokens":"int","timestamp":"str"}
                },
                "auth": "Basic Auth (admin / password)",
                "data_sources": ["Microsoft Graph API (Mail, Calendar, Chat, People)", "Azure OpenAI GPT-5.4"],
                "refresh_interval": "15s poll, GPT-5.4 only on data change",
                "architecture": "Graph API → Python data collection → GPT-5.4 analysis → JSON API → HTML Dashboard"
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(schema, indent=2).encode('utf-8'))
        elif path == '/api/health':
            # Health check for production monitoring
            import datetime as dt
            meta = current_data.get('_meta', {})
            last_analysis = meta.get('timestamp', 'never')
            health = {
                'status': 'ok' if current_data else 'warming_up',
                'email_hours': EMAIL_HOURS,
                'poll_interval': POLL_INTERVAL,
                'last_analysis': last_analysis,
                'data_layer': os.getenv('USE_DATA_LAYER', 'false'),
                'emails_count': len(current_data.get('priority_emails', [])),
                'contacts_count': len(current_data.get('contact_profiles', [])),
                'uptime_check': dt.datetime.now().isoformat(),
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health).encode())
        elif path == '/api/insights':
            # CosmosDB historical insights
            try:
                from data_layer import _get_cosmos_db
                db = _get_cosmos_db()
                # 1. Analysis history (task count trend)
                analyses = list(db.get_container_client('analyses').query_items(
                    'SELECT c.timestamp, c.action_items, c.insights, c.contacts_flagged, c.token_cost FROM c WHERE c.user_id = "default" ORDER BY c.timestamp DESC',
                    enable_cross_partition_query=True
                ))
                # 2. Contact profiles with evolution
                profiles = list(db.get_container_client('profiles').query_items(
                    'SELECT c.contact_name, c.communication_style, c.sentiment, c.interaction_frequency, c.recent_topics, c.updated_at, c.tip FROM c WHERE c.user_id = "default" AND c.type = "contact"',
                    enable_cross_partition_query=True
                ))
                result = {
                    'analysis_history': [
                        {
                            'time': a.get('timestamp', ''),
                            'tasks': len(a.get('action_items', [])),
                            'task_list': a.get('action_items', [])[:3],
                            'insights': a.get('insights', [])[:2],
                            'attention': a.get('contacts_flagged', []),
                            'tokens': a.get('token_cost', {}).get('total_tokens', 0),
                        }
                        for a in analyses[:20]
                    ],
                    'contact_evolution': [
                        {
                            'name': p.get('contact_name', ''),
                            'style': p.get('communication_style', ''),
                            'sentiment': p.get('sentiment', ''),
                            'frequency': p.get('interaction_frequency', ''),
                            'topics': p.get('recent_topics', []),
                            'tip': p.get('tip', ''),
                            'updated': p.get('updated_at', ''),
                        }
                        for p in profiles
                    ],
                    'total_analyses': len(analyses),
                    'total_tokens_used': sum(a.get('token_cost', {}).get('total_tokens', 0) for a in analyses if isinstance(a.get('token_cost'), dict)),
                }
                resp = json.dumps(result, ensure_ascii=False, default=str).encode()
            except Exception as e:
                resp = json.dumps({'error': str(e)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_error(404)
    
    def do_POST(self):
        if not self.require_auth():
            return
        path = urlparse(self.path).path
        if path == '/api/send-mail':
            length = int(self.headers.get('Content-Length', 0))
            if length <= 0 or length > MAX_POST_BODY:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ok': False, 'error': f'Invalid Content-Length (max {MAX_POST_BODY})'}).encode())
                return
            body = json.loads(self.rfile.read(length))
            # Validate required fields
            for field in ('to', 'subject', 'body'):
                if field not in body or not body[field]:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'ok': False, 'error': f'Missing required field: {field}'}).encode())
                    return
            try:
                from morning_sweep import get_token, GRAPH_BASE, USE_SP_AUTH, SP_TARGET_USER
                import requests as req
                token = get_token()
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                msg = {
                    'message': {
                        'subject': body['subject'],
                        'body': {'contentType': 'Text', 'content': body['body']},
                        'toRecipients': [{'emailAddress': {'address': body['to']}}],
                    },
                    'saveToSentItems': 'true'
                }
                # Add attachments if present
                attachments = body.get('attachments', [])
                if attachments:
                    msg['message']['attachments'] = [
                        {
                            '@odata.type': '#microsoft.graph.fileAttachment',
                            'name': att.get('name', 'attachment'),
                            'contentType': att.get('contentType', 'application/octet-stream'),
                            'contentBytes': att.get('contentBytes', ''),
                        }
                        for att in attachments
                    ]
                # SP mode: /me → /users/{target}
                send_path = f'/users/{SP_TARGET_USER}/sendMail' if USE_SP_AUTH else '/me/sendMail'
                r = req.post(f'{GRAPH_BASE}{send_path}', headers=headers, json=msg, timeout=30)
                if r.status_code == 202:
                    resp = json.dumps({'ok': True}).encode()
                    print(f"  ✉️  Email sent to {body['to']}: {body['subject']}")
                else:
                    resp = json.dumps({'ok': False, 'error': r.text[:200]}).encode()
            except Exception as e:
                resp = json.dumps({'ok': False, 'error': str(e)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resp)
        elif path == '/api/optimize-draft':
            length = int(self.headers.get('Content-Length', 0))
            if length <= 0 or length > MAX_POST_BODY:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid Content-Length'}).encode())
                return
            body = json.loads(self.rfile.read(length))
            try:
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    azure_endpoint=os.getenv("AOAI_ENDPOINT", ""),
                    api_key=os.getenv("AOAI_KEY", ""),
                    api_version="2025-04-01-preview",
                )
                persona = body.get('persona', {})
                prompt = f"""Rewrite this email draft to match the recipient's communication style.

Recipient: {persona.get('name', '')}
Communication style: {persona.get('style', '')}
Relationship: {persona.get('relationship', '')}
Tip: {persona.get('tip', '')}

Original subject: {body.get('subject', '')}
Original draft:
{body.get('original_draft', '')}

Rules:
- If style is "direct": use short sentences, bullet points, action-oriented, no pleasantries
- If style is "formal": professional tone, proper salutations, structured paragraphs
- If style is "detail-oriented": include specifics, data points, step-by-step details
- If style is "casual": friendly tone, conversational, brief
- Keep the same core message and action items
- Output ONLY the rewritten email text, nothing else."""

                response = client.chat.completions.create(
                    model=os.getenv("AOAI_DEPLOYMENT", "gpt-5.4"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_completion_tokens=500,
                )
                optimized = response.choices[0].message.content.strip()
                print(f"  🎭 Draft optimized for {persona.get('name','')} ({persona.get('style','')})")
                resp = json.dumps({'optimized': optimized}).encode()
            except Exception as e:
                resp = json.dumps({'error': str(e)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resp)
        elif path == '/api/refresh':
            # Manual trigger: force re-poll and re-analyze, optionally change time range
            global last_hash, EMAIL_HOURS
            try:
                length = int(self.headers.get('Content-Length', 0))
                if 0 < length <= MAX_POST_BODY:
                    body = json.loads(self.rfile.read(length))
                    hours = body.get('hours')
                    if hours and isinstance(hours, int) and 1 <= hours <= 720:
                        with lock:
                            EMAIL_HOURS = hours
                        print(f"  🔄 Email range changed to {hours}h")
                with lock:
                    last_hash = ""  # Reset hash to force re-analysis
                print(f"  🔄 Manual refresh triggered! (range: {EMAIL_HOURS}h)")
                resp = json.dumps({'ok': True, 'hours': EMAIL_HOURS}).encode()
            except Exception as e:
                resp = json.dumps({'ok': False, 'error': str(e)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        if '/api/' not in str(args[0]):
            print(f"  🌐 {args[0]}")

if __name__ == '__main__':
    # Load existing data if available
    try:
        if os.path.exists('morning_sweep_output.json'):
            with open('morning_sweep_output.json') as f:
                current_data = json.load(f)
            print("📂 Loaded existing data from morning_sweep_output.json")
    except Exception as e:
        print(f"⚠️ Could not load existing data: {e} — starting fresh")

    if AUTH_PASS in ('changeme', ''):
        print("\n⚠️  WARNING: DASHBOARD_PASSWORD is set to default. Change it in .env before production use!\n")

    print("=" * 60)
    print("🌅 Morning Sweep — LIVE Dashboard")
    print(f"   👉 http://localhost:{PORT}")
    print(f"   Poll: every {POLL_INTERVAL}s | GPT-5.4: only on data change")
    print("=" * 60)

    t = threading.Thread(target=poll_and_analyze, daemon=True)
    t.start()

    class ThreadedServer(http.server.ThreadingHTTPServer):
        daemon_threads = True
    server = ThreadedServer(('0.0.0.0', PORT), Handler)
    print(f"\n🌐 Server running → open http://localhost:{PORT}")
    print("   Press Ctrl+C to stop\n")
    server.serve_forever()
