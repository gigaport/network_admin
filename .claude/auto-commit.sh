#!/bin/bash
# Stop hook: Claude 의 한 응답 턴이 끝났을 때 변경분이 있으면 자동 커밋·푸시.
# - stop_hook_active=true 인 경우(이미 Stop 훅 안에서 실행 중) 무한 루프 방지 위해 즉시 종료
# - 변경분이 없으면 아무 일도 안 함
# - 실패해도 종료 코드 0 (Claude 흐름을 막지 않음)
#
# 호출: settings.local.json 의 hooks.Stop 에서 stdin 으로 JSON 수신
set -u

REPO=/home/sysmon/network_admin
LOG="$REPO/.claude/auto-commit.log"
BRANCH=main

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# 1) stdin JSON 에서 stop_hook_active 확인 (재귀 방지)
STDIN_JSON="$(cat 2>/dev/null || true)"
if [ -n "$STDIN_JSON" ]; then
    if command -v jq >/dev/null 2>&1; then
        if [ "$(printf '%s' "$STDIN_JSON" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
            log "skip: stop_hook_active=true (re-entry guard)"
            exit 0
        fi
    fi
fi

cd "$REPO" 2>/dev/null || { log "abort: cannot cd to $REPO"; exit 0; }

# 2) 변경분 확인
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    # 변경 없음 — 로그도 남기지 않음 (소음 방지)
    exit 0
fi

CHANGES_SUMMARY=$(git status --porcelain | head -20 | tr '\n' ' ')
log "changes detected: $CHANGES_SUMMARY"

# 3) 스테이지 + 커밋
if ! git add -A 2>>"$LOG"; then
    log "abort: git add failed"
    exit 0
fi

COMMIT_MSG="auto: $(date '+%Y-%m-%d %H:%M:%S') Claude session"
if ! git commit -m "$COMMIT_MSG" >>"$LOG" 2>&1; then
    log "abort: git commit failed (possibly nothing staged after ignore)"
    exit 0
fi

# 4) 푸시
if GIT_TERMINAL_PROMPT=0 git push origin "$BRANCH" >>"$LOG" 2>&1; then
    log "ok: pushed to origin/$BRANCH"
else
    log "warn: git push failed (commit kept locally for next push attempt)"
fi

exit 0
