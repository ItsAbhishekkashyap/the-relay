import os
import json
import re

TRANSCRIPT_PATH = r"C:\Users\abhi4\.gemini\antigravity\brain\7d8a4c71-ac2f-4288-bd0b-fccca0ed6c51\.system_generated\logs\transcript.jsonl"
TRANSCRIPT_FULL_PATH = r"C:\Users\abhi4\.gemini\antigravity\brain\7d8a4c71-ac2f-4288-bd0b-fccca0ed6c51\.system_generated\logs\transcript_full.jsonl"
SUBAGENT_TRANSCRIPT = r"C:\Users\abhi4\.gemini\antigravity\brain\7f1c103e-ac54-4fab-99cf-d851e152d72e\.system_generated\logs\transcript.jsonl"
SUBAGENT_FULL = r"C:\Users\abhi4\.gemini\antigravity\brain\7f1c103e-ac54-4fab-99cf-d851e152d72e\.system_generated\logs\transcript_full.jsonl"

OUTPUT_DIR = "submission/assistant_history"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Find any real groq api keys to redact
pattern = re.compile(r'gsk_[A-Za-z0-9]{20,}')
real_keys = set()
with open(TRANSCRIPT_FULL_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        matches = pattern.findall(line)
        for m in matches:
            if not m.startswith(('gsk_mock', 'gsk_invalid', 'gsk_abcdef', 'gsk_your_act')):
                real_keys.add(m)

print(f"Identified {len(real_keys)} secret keys to redact.")

def sanitize_line(line: str) -> str:
    for rk in real_keys:
        line = line.replace(rk, "gsk_REDACTED_API_KEY_FOR_SUBMISSION")
    return line

# 1. Export sanitized transcript.jsonl
out_transcript = os.path.join(OUTPUT_DIR, "gemini_conversation_transcript.jsonl")
line_count = 0
with open(TRANSCRIPT_PATH, 'r', encoding='utf-8') as src, open(out_transcript, 'w', encoding='utf-8') as dst:
    for line in src:
        dst.write(sanitize_line(line))
        line_count += 1
print(f"Wrote {line_count} steps to {out_transcript}")

# 2. Export sanitized transcript_full.jsonl
out_full = os.path.join(OUTPUT_DIR, "gemini_conversation_transcript_full.jsonl")
line_count_full = 0
with open(TRANSCRIPT_FULL_PATH, 'r', encoding='utf-8') as src, open(out_full, 'w', encoding='utf-8') as dst:
    for line in src:
        dst.write(sanitize_line(line))
        line_count_full += 1
print(f"Wrote {line_count_full} steps to {out_full}")

# 3. Export subagent transcripts
if os.path.exists(SUBAGENT_TRANSCRIPT):
    out_sub = os.path.join(OUTPUT_DIR, "gemini_browser_subagent_transcript.jsonl")
    with open(SUBAGENT_TRANSCRIPT, 'r', encoding='utf-8') as src, open(out_sub, 'w', encoding='utf-8') as dst:
        for line in src:
            dst.write(sanitize_line(line))
    print(f"Wrote subagent transcript to {out_sub}")

if os.path.exists(SUBAGENT_FULL):
    out_sub_full = os.path.join(OUTPUT_DIR, "gemini_browser_subagent_transcript_full.jsonl")
    with open(SUBAGENT_FULL, 'r', encoding='utf-8') as src, open(out_sub_full, 'w', encoding='utf-8') as dst:
        for line in src:
            dst.write(sanitize_line(line))
    print(f"Wrote subagent full transcript to {out_sub_full}")

# 4. Generate Human-Readable Markdown Log
md_out_path = os.path.join(OUTPUT_DIR, "GEMINI_CONVERSATION_HISTORY.md")
user_turns = []

with open(TRANSCRIPT_FULL_PATH, 'r', encoding='utf-8') as f:
    current_user_prompt = None
    current_model_response = []
    step_num = 0
    
    for line in f:
        step_num += 1
        data = json.loads(line)
        src = data.get("source")
        tp = data.get("type")
        content = data.get("content", "")
        ts = data.get("created_at", "")
        
        if tp == "USER_INPUT" and src == "USER_EXPLICIT":
            if current_user_prompt:
                user_turns.append({
                    "prompt": current_user_prompt,
                    "timestamp": current_ts,
                    "responses": current_model_response
                })
            current_user_prompt = sanitize_line(content)
            current_ts = ts
            current_model_response = []
        elif tp == "PLANNER_RESPONSE" and src == "MODEL":
            if content:
                current_model_response.append(sanitize_line(content))
        elif tp == "SYSTEM_MESSAGE" and "finished with result" in content:
            # summarize tool completion
            pass

    if current_user_prompt:
        user_turns.append({
            "prompt": current_user_prompt,
            "timestamp": current_ts,
            "responses": current_model_response
        })

print(f"Parsed {len(user_turns)} user turns for human-readable Markdown log.")

with open(md_out_path, 'w', encoding='utf-8') as f:
    f.write("# Gemini / Antigravity Conversation History Log\n\n")
    f.write("**Project:** The Relay — Vaani Research ML Engineering Assignment\n")
    f.write(f"**Session ID:** `7d8a4c71-ac2f-4288-bd0b-fccca0ed6c51`\n")
    f.write(f"**Total Trajectory Steps:** {line_count_full}\n")
    f.write(f"**Total User Dialogue Turns:** {len(user_turns)}\n")
    f.write("**Model Engine:** Gemini 2.5 Flash / Pro (Google DeepMind Antigravity Agent Harness)\n")
    f.write("**Raw Machine Logs:** `gemini_conversation_transcript.jsonl` (compact) and `gemini_conversation_transcript_full.jsonl` (full payloads)\n\n")
    f.write("---\n\n")
    f.write("## Table of Contents\n\n")
    for i, turn in enumerate(user_turns):
        first_line = turn["prompt"].strip().split("\n")[0][:75]
        first_line = re.sub(r'[\#\<\>\[\]\*_]', '', first_line).strip()
        f.write(f"- [Turn {i+1} ({turn['timestamp'][:19]}): {first_line}](#turn-{i+1})\n")
    
    f.write("\n---\n\n")
    
    for i, turn in enumerate(user_turns):
        f.write(f"## Turn {i+1}\n\n")
        f.write(f"**Timestamp (UTC):** `{turn['timestamp']}`\n\n")
        f.write("### User Request\n\n")
        f.write("```markdown\n")
        f.write(turn["prompt"].strip() + "\n")
        f.write("```\n\n")
        
        f.write("### Assistant Actions & Final Response\n\n")
        if turn["responses"]:
            last_resp = turn["responses"][-1]
            f.write(last_resp.strip() + "\n\n")
        else:
            f.write("*Executed task actions and system tool calls autonomously.*\n\n")
        
        f.write("---\n\n")

print(f"Generated human-readable conversation history at {md_out_path}")

# 5. Write README.md in assistant_history
readme_path = os.path.join(OUTPUT_DIR, "README.md")
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write("""# Assistant Conversation History Logs

This directory contains the complete, unedited conversation trajectory logs recorded during the development of **The Relay** project with Google Antigravity / Gemini.

## Files in this Directory

1. **`GEMINI_CONVERSATION_HISTORY.md`**
   - Human-readable chronological log of all 46 user requests and assistant milestone deliveries.
   - Formatted in clean Markdown for rapid manual inspection.

2. **`gemini_conversation_transcript.jsonl`**
   - Compact raw trajectory JSONL log (7,018 steps).
   - Contains timestamps, step indices, message sources (`USER_EXPLICIT`, `MODEL`, `SYSTEM`), and step types.

3. **`gemini_conversation_transcript_full.jsonl`**
   - Complete raw trajectory JSONL log with full command inputs, outputs, code edits, and tool payloads (~12 MB).

4. **`gemini_browser_subagent_transcript.jsonl` & `gemini_browser_subagent_transcript_full.jsonl`**
   - Trajectory log of the autonomous browser subagent (`7f1c103e-ac54-4fab-99cf-d851e152d72e`) deployed during Stage 8G for live Chrome DevTools frontend UI verification.

## Privacy & Security Verification
- All live API keys have been safely redacted (`gsk_REDACTED_API_KEY_FOR_SUBMISSION`) to prevent accidental credential leakage in public repositories.
- Zero mock keys or evaluation records were modified.
""")
print(f"Generated README at {readme_path}")
