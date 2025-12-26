cd /root/gdpval-web

# Kill existing processes
pkill -f 'uvicorn.*main:app' 2>/dev/null
pkill -f 'next start' 2>/dev/null
sleep 2

# Start backend on port 8000
cd /root/gdpval-web/backend
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/gdpval-backend.log 2>&1 &
echo "Backend started on port 8000"

# Start frontend on port 54402
cd /root/gdpval-web/frontend
nohup npx next start -p 54402 > /tmp/gdpval-frontend.log 2>&1 &
echo "Frontend started on port 54402"

sleep 3
echo "Services running:"
ps aux | grep -E 'uvicorn|next' | grep -v grep
