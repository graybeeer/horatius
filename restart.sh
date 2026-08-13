pkill -f "python ddalgi_app.py"
sleep 2
nohup python ddalgi_app.py > nohup.out 2>&1 &
tail -f nohup.out
