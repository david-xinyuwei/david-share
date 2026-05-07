"""
Auto-refresh Morning Sweep Server
- Every 60 seconds: pull Graph API data → GPT-5.4 analysis → update dashboard
- Serves dashboard on http://localhost:8088
- Browser auto-refreshes every 60s
"""
import http.server
import threading
import time
import json
import os
import sys

PORT = 8088
REFRESH_INTERVAL = 60  # seconds

def refresh_data():
    """Pull latest data from Graph API + GPT-5.4 and rebuild dashboard."""
    from morning_sweep import get_token, fetch_recent_emails, fetch_today_calendar, fetch_recent_chats, fetch_user_profile, fetch_people, analyze_with_gpt54
    
    try:
        token = get_token()
        profile = fetch_user_profile(token)
        emails = fetch_recent_emails(token, hours=24)
        calendar = fetch_today_calendar(token)
        chats = fetch_recent_chats(token)
        people = fetch_people(token)
        
        print(f"  📧 {len(emails)} emails | 📅 {len(calendar)} events | 💬 {len(chats)} chats | 👥 {len(people)} contacts")
        
        result = analyze_with_gpt54(emails, calendar, chats, profile, people)
        if result:
            with open('morning_sweep_output.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            rebuild_dashboard(result)
            return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
    return False

def rebuild_dashboard(data):
    """Embed data into HTML dashboard."""
    with open('morning_sweep_dashboard_template.html', encoding='utf-8') as f:
        html = f.read()
    
    old = "fetch('morning_sweep_output.json').then(r=>r.json()).then(data => {"
    new = 'const data = ' + json.dumps(data, ensure_ascii=False, default=str) + ';\n{'
    html = html.replace(old, new)
    html = html.replace('});\n</script>', '}\n</script>')
    
    # Add auto-refresh meta tag
    html = html.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n<meta http-equiv="refresh" content="65">')
    
    with open('morning_sweep_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)

def auto_refresh_loop():
    """Background thread: refresh data every REFRESH_INTERVAL seconds."""
    while True:
        now = time.strftime("%H:%M:%S")
        print(f"\n🔄 [{now}] Refreshing Morning Sweep...")
        if refresh_data():
            print(f"  ✅ Dashboard updated. Browser will auto-refresh.")
        else:
            print(f"  ⚠️  Refresh failed, keeping previous data.")
        time.sleep(REFRESH_INTERVAL)

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        if '.html' in str(args[0]):
            print(f"  🌐 Served dashboard to browser")

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 60)
    print("🌅 Morning Sweep — Auto-Refresh Server")
    print(f"   Dashboard: http://localhost:{PORT}/morning_sweep_dashboard.html")
    print(f"   Refresh interval: {REFRESH_INTERVAL}s")
    print("=" * 60)
    
    # Initial refresh
    print("\n🚀 Initial data load...")
    refresh_data()
    
    # Start background refresh thread
    t = threading.Thread(target=auto_refresh_loop, daemon=True)
    t.start()
    
    # Start HTTP server
    server = http.server.HTTPServer(('0.0.0.0', PORT), QuietHandler)
    print(f"\n🌐 Server running at http://localhost:{PORT}/morning_sweep_dashboard.html")
    print("   Press Ctrl+C to stop\n")
    server.serve_forever()
