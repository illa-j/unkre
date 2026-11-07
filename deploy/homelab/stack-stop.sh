#!/data/data/com.termux/files/usr/bin/bash
export PATH="$PREFIX/bin:$HOME/bin:$PATH"

pkill -9 -f '[s]upervisord -n' 2>/dev/null || true
pkill -9 -f '[e]xec supervisord' 2>/dev/null || true
pkill -9 -f '[m]inio server' 2>/dev/null || true
pkill -9 -f '[u]vicorn adapters' 2>/dev/null || true
pkill -9 -f '[n]ext-server' 2>/dev/null || true
pkill -9 -f '[a]rq adapters' 2>/dev/null || true
pkill -9 -f '[a]dapters.bot.main' 2>/dev/null || true
