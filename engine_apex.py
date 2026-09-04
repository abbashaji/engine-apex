import os
import sys
import json
import time
import subprocess
from duckduckgo_search import DDGS
import chromadb
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("[!] Error: GEMINI_API_KEY not found.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)
# استفاده از مدل‌های فعال در اکانت شما
DEFAULT_MODEL = "gemini-2.5-flash"
FAST_MODEL = "gemini-2.5-flash-lite"

def generate_text(prompt, temperature=0.4, model_name=DEFAULT_MODEL):
    time.sleep(2)  # رعایت سقف RPM
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature)
    )
    return response.text or ""

def search_web(query, max_results=4):
    print(f"[+] Searching web for: {query}")
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No web data found."
        lines = []
        for r in results:
            t = r.get("title", "")
            b = r.get("body", "")
            lines.append(f"- {t}: {b}")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"

def setup_memory():
    chroma_client = chromadb.PersistentClient(path="./.vector_memory")
    collection = chroma_client.get_or_create_collection(name="apex_knowledge")
    return collection

def query_memory(collection, text, n_results=2):
    try:
        count = collection.count()
        if count == 0:
            return "Initial run: memory is empty."
        res = collection.query(query_texts=[text], n_results=min(n_results, count))
        if res and res.get("documents") and res["documents"][0]:
            return "\n".join(res["documents"][0])
        return "No relevant past entries."
    except Exception as e:
        return f"Memory error: {e}"

def run_python_code(code_str):
    test_file = "_sandbox_test.py"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(code_str)
    try:
        res = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=15
        )
        if os.path.exists(test_file):
            os.remove(test_file)
        if res.returncode == 0:
            return True, res.stdout.strip()
        else:
            return False, res.stderr.strip()
    except subprocess.TimeoutExpired:
        if os.path.exists(test_file):
            os.remove(test_file)
        return False, "Execution timeout (>15s)."
    except Exception as e:
        if os.path.exists(test_file):
            os.remove(test_file)
        return False, str(e)

def extract_code_block(text):
    tag = chr(96) * 3
    if tag not in text:
        return ""
    parts = text.split(tag)
    if len(parts) >= 3:
        code_section = parts[1]
        lines = code_section.split("\n")
        if lines and lines[0].strip().lower().startswith("python"):
            return "\n".join(lines[1:]).strip()
        return code_section.strip()
    return ""

def parse_score(text):
    for line in text.split("\n"):
        if "SCORE:" in line:
            clean = "".join([c for c in line if c.isdigit()])
            if clean:
                try:
                    return int(clean)
                except ValueError:
                    pass
    return 70

def main():
    if not os.path.exists("problem.txt"):
        print("[!] problem.txt not found. Creating default problem.txt...")
        with open("problem.txt", "w", encoding="utf-8") as f:
            f.write("طراحی یک معماری نرم‌افزاری توزیع‌شده با قابلیت همگام‌سازی خودکار")

    with open("problem.txt", "r", encoding="utf-8") as f:
        problem = f.read().strip()

    print(f"\n[+] Processing problem:\n{problem}\n")

    memory = setup_memory()
    past_learnings = query_memory(memory, problem)

    search_prompt = f"Provide a compact 3-word query to find recent technological breakthroughs for: {problem}. Output only the 3 words."
    sq = generate_text(search_prompt, temperature=0.2, model_name=FAST_MODEL).strip().replace('"', '').replace('\n', '')
    web_data = search_web(sq)

    iteration = 1
    max_iterations = 3
    converged = False
    current_solution = ""
    critique_history = []
    fence = chr(96) * 3

    while iteration <= max_iterations and not converged:
        print(f"\n--- Iteration {iteration}/{max_iterations} ---")

        radical_prompt = (
            "You are AGENT ALPHA (Radical Transmorphic Architect).\n"
            f"Problem: {problem}\n"
            f"Memory Insights: {past_learnings}\n"
            f"Web Grounding: {web_data}\n"
            f"Critique History: {json.dumps(critique_history, ensure_ascii=False)}\n\n"
            "TASK:\n"
            "1. Synthesize a radical, high-order, non-obvious solution.\n"
            f"2. Provide a self-contained Python script enclosed in {fence}python ... {fence} that models or tests the core quantitative claims.\n"
        )
        alpha_res = generate_text(radical_prompt, temperature=0.8, model_name=DEFAULT_MODEL)

        code_block = extract_code_block(alpha_res)
        code_report = "No code provided."
        if code_block:
            print("[+] Running simulation code in sandbox...")
            success, output = run_python_code(code_block)
            if success:
                code_report = f"Success:\n{output}"
                print(f"[✓] Code Output:\n{output}")
            else:
                code_report = f"Execution Error:\n{output}"
                print(f"[✗] Code Error:\n{output}")

        beta_prompt = (
            "You are AGENT BETA (Nihilistic Adversary).\n"
            f"Problem: {problem}\n"
            f"Proposed Solution: {alpha_res}\n"
            f"Sandbox Output: {code_report}\n\n"
            "TASK:\n"
            "Brutally critique this solution. Point out operational bottlenecks, thermodynamic impossibilities, and economic flaws.\n"
            "Score the viability from 0 to 100.\n"
            "Format:\nSCORE: <number>\nCRITIQUE: <ruthless critique>"
        )
        beta_res = generate_text(beta_prompt, temperature=0.3, model_name=FAST_MODEL)
        score = parse_score(beta_res)
        print(f"[+] Stability Score: {score}/100")

        if score >= 90 or iteration == max_iterations:
            converged = True
            current_solution = alpha_res
            critique_history.append({"iteration": iteration, "score": score, "critique": beta_res, "code_status": code_report})
            print("[+] Target convergence reached.")
            break
        else:
            critique_history.append({"iteration": iteration, "score": score, "critique": beta_res, "code_status": code_report})
            iteration += 1

    print("\n[+] Synthesizing Final Blueprint...")
    final_prompt = (
        "You are THE SUPREME COGNITIVE ARCHITECT.\n"
        f"Problem: {problem}\n"
        f"Evolutionary Journey: {json.dumps(critique_history, ensure_ascii=False)}\n"
        f"Final Refined Thesis: {current_solution}\n\n"
        "TASK:\n"
        "Produce an authoritative, deeply structured operational blueprint in Persian (Markdown).\n"
        "Include sections:\n"
        "# ۱. معماری و استراتژی نامتقارن\n"
        "# ۲. بینش‌های تجربی استخراج‌شده از کاوش وب\n"
        "# ۳. اعتبارسنجی محاسباتی و نتایج شبیه‌سازی کد پایتون\n"
        "# ۴. واکسیناسیون ریسک‌ها (پاسخ قطعی به نقدهای ویرانگر)\n"
        "# ۵. فازبندی گام‌به‌گام برای پیاده‌سازی فیزیکی\n"
    )
    final_report = generate_text(final_prompt, temperature=0.4, model_name=DEFAULT_MODEL)

    with open("APEX_BLUEPRINT.md", "w", encoding="utf-8") as f:
        f.write(final_report)

    try:
        run_id = os.environ.get("GITHUB_RUN_ID", "local")
        memory.add(
            documents=[f"Problem: {problem} | Insights: {final_report[:500]}"],
            metadatas=[{"score": score}],
            ids=[f"run_{run_id}"]
        )
    except Exception as e:
        print(f"[!] Memory update skipped: {e}")

    print("\n[✓] Finished successfully. Output saved to APEX_BLUEPRINT.md")

if __name__ == "__main__":
    main()
