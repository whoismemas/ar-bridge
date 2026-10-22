#!/usr/bin/env bash
# ar_bridge_watchdog.sh — keep ar_bridge.py alive, restart if dead.
# Runs from cron every minute. Silent when healthy (watchdog pattern).

BRIDGE=/home/opc/ar_bridge.py
LOG=/tmp/ar_bridge.log
PIDFILE=/tmp/ar_bridge_watchdog.pid

# single instance guard
[ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null && exit 0
echo $$ > "$PIDFILE"
trap 'rm -f $PIDFILE' EXIT

if ! curl -s --max-time 5 http://127.0.0.1:20132/health | grep -q '"ok": true'; then
    # dead or hung -> kill leftovers, restart
    pkill -f "python3.9 ar_bridge.py" 2>/dev/null
    sleep 1
    nohup python3.9 "$BRIDGE" >> "$LOG" 2>&1 &
    echo "$(date '+%F %T') restarted ar_bridge (pid $!)" >> /tmp/ar_bridge_watchdog.log
fi
