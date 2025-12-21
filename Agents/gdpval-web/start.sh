#!/bin/bash
# GDPVAL Web 启动脚本

cd "$(dirname "$0")"

echo "🚀 启动 GDPVAL Web..."
echo ""

# 启动后端
echo "📦 启动 FastAPI 后端 (port 8000)..."
cd backend
pip install -r requirements.txt -q
python main.py &
BACKEND_PID=$!
cd ..

# 等待后端启动
sleep 2

# 启动前端
echo "🎨 启动 Next.js 前端 (port 3000)..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ 服务已启动!"
echo "   - 后端 API: http://localhost:8000"
echo "   - 前端 UI:  http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待中断
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
