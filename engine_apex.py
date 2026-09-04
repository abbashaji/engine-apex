import os
import sys
import json
import subprocess
import traceback
from duckduckgo_search import DDGS
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai

# ۱. پیکربندی API و مدل‌ها
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("[!] خطا: GEMINI_API_KEY تنظیم نشده است.")
    sys.exit(1)

genai.configure(api_key=API_KEY)
# استفاده از مدل فوق‌سریع و هوشمند با پنجره زمینه وسیع
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"temperature": 0.4}
)
radical_model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"temperature": 0.8} # دمای بالاتر برای تفکر جهشی
)

# ۲. ابزار جستجوی زنده وب
def search_web(query, max_results=4):
    print(f"[🔍] در حال کاوش زنده وب برای: {query}...")
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "هیچ داده‌ای در وب یافت نشد."
        return "\n".join([f"- {r['title']}: {r['body']} (لینک: {r['href']})" for r in results])
    except Exception as e:
        return f"خطای جستجو: {str(e)}"

# ۳. حافظه برداری محلی (ChromaDB)
def setup_memory():
    client = chromadb.PersistentClient(path="./.vector_memory")
    collection = client.get_or_create_collection(name="apex_knowledge")
    return collection

def query_memory(collection, text, n_results=2):
    try:
        count = collection.count()
        if count == 0:
            return "حافظه قبلی خالی است (اولین اجرای سیستم)."
        res = collection.query(query_texts=[text], n_results=min(n_results, count))
        return "\n".join(res['documents'][0]) if res['documents'] else "یافته‌ای نبود."
    except Exception as e:
        return "خطا در بازیابی حافظه."

# ۴. جعبه‌شنی اجرای کد (Execution Sandbox)
def run_python_code(code_str):
    """کد پایتون مدل را مستقیماً در لینوکس اجرا و اعتبارسنجی می‌کند"""
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
        os.remove(test_file)
        if res.returncode == 0:
            return True, res.stdout.strip()
        else:
            return False, res.stderr.strip()
    except subprocess.TimeoutExpired:
        if os.path.exists(test_file): os.remove(test_file)
        return False, "خطا: اجرای کد بیش از حد طول کشید (Timeout)."
    except Exception as e:
        if os.path.exists(test_file): os.remove(test_file)
        return False, str(e)

# -------------------------------------------------------------
# اجرای چرخه استنتاج اصلی
# -------------------------------------------------------------
def main():
    if not os.path.exists("problem.txt"):
        print("[!] فایل problem.txt یافت نشد.")
        return

    with open("problem.txt", "r", encoding="utf-8") as f:
        problem = f.read().strip()

    print(f"\n[🚀] شروع چرخه سرحد مطلق برای مسئله:\n>>> {problem}\n")

    # فاز ۱: فراخوانی حافظه و زمینه‌یابی
    memory = setup_memory()
    past_learnings = query_memory(memory, problem)
    
    # فاز ۲: استخراج سرچ‌کوئری و کاوش زنده وب
    search_prompt = f"Produce a compact 3-word web search query to find the absolute latest tech/research on: {problem}. Return ONLY the query."
    sq = model.generate_content(search_prompt).text.strip().replace('"', '')
    web_data = search_web(sq)

    # فاز ۳: حلقه تکاملی خوداصلاح‌گر (Evolution Loop)
    iteration = 1
    max_iterations = 3
    converged = False
    current_solution = ""
    critique_history = []

    while iteration <= max_iterations and not converged:
        print(f"\n═══════════════════════════════════════════════")
        print(f"[*] دور تکاملی {iteration}/{max_iterations}")
        print(f"═══════════════════════════════════════════════")

        # الف) عامل رادیکال: تولید راه‌حل + اسکریپت اثبات منطقی/محاسباتی
        radical_prompt = f"""
You are AGENT ALPHA (Radical Transmorphic Architect).
Problem: {problem}
Past Insights from Memory: {past_learnings}
Live Web Grounding: {web_data}
Previous Critiques: {json.dumps(critique_history, ensure_ascii=False)}

TASK:
1. Provide a radically innovative, non-obvious solution leveraging structural isomorphisms.
2. Write a clean, self-contained Python script enclosed in
```python ... 
``` that models, simulates, or stress-tests the key mathematical, physical, or logical claims of this solution. The script must run in under 5 seconds and print key verification metrics.
"""
        alpha_res = radical_model.generate_content(radical_prompt).text
        
        # استخراج و تست کد پایتون
        code_block = ""
        if "
```python" in alpha_res:
code_block = alpha_res.split("
```python")[1].split("
```")[0].strip()

code_exec_report = "بدون کد شبیه‌سازی."
if code_block:
print("[⚙️] در حال اعتبارسنجی فرضیه در لینوکس...")
success, output = run_python_code(code_block)
if success:
code_exec_report = f"موفقیت‌آمیز در اجرا:\n{output}"
print(f"[✓] تست کد موفقیت‌آمیز بود:\n{output}")
else:
code_exec_report = f"شکست در اعتبارسنجی کد/تناقض داده:\n{output}"
print(f"[✗] باگ یا خطا در شبیه‌سازی:\n{output}")

# ب) عامل تخریب‌گر بدبین: نقد بی‌رحمانه بر اساس کد و واقعیت
beta_prompt = f"""
You are AGENT BETA (Nihilistic Stress-Tester).
Problem: {problem}
Proposed Solution: {alpha_res}
Code Simulation Verification Output: {code_exec_report}

TASK:
Brutally tear down this idea. Attack assumptions, thermodynamics, operational bottlenecks, unit economics, and edge cases.
Rate the overall soundness of the solution from 0 to 100.
Format your output exactly as:
SCORE: <score>
CRITIQUE: <your ruthless critique>
"""
beta_res = model.generate_content(beta_prompt).text

# استخراج نمره
score = 70
try:
for line in beta_res.split("\n"):
if "SCORE:" in line:
score = int(''.join(filter(str.isdigit, line)))
break
except:
pass

print(f"[📊] نمره پایداری در این دور: {score}/100")

if score >= 90 or iteration == max_iterations:
converged = True
current_solution = alpha_res
critique_history.append({"iteration": iteration, "score": score, "critique": beta_res, "code_status": code_exec_report})
print("[★] سیستم به همگرایی و آستانه پایداری رسید.")
break
else:
critique_history.append({"iteration": iteration, "score": score, "critique": beta_res, "code_status": code_exec_report})
iteration += 1

# فاز ۴: سنتز دیالکتیک نهایی و تدوین سند اجرایی
print("\n[*] در حال تدوین گزارش پایانی توسط معمار سنتز...")
final_prompt = f"""
You are THE SUPREME COGNITIVE ARCHITECT.
Problem: {problem}
Web Context: {web_data}
Full Evolutionary Journey & Stress-Tests: {json.dumps(critique_history, ensure_ascii=False)}
Last Thesis: {current_solution}

TASK:
Write an authoritative, mathematically & operationally robust blueprint in Persian (Markdown).
Structure:
# ۱. منشور معماری و استراتژی نامتقارن
# ۲. شواهد زنده تجربی و بینش‌های کشف‌شده از وب
# ۳. اثبات اعتبارسنجی شبیه‌سازی محاسباتی (Code Grounding)
# ۴. واکسیناسیون ریسک‌ها (چگونه نقدهای ویرانگر خنثی شدند)
# ۵. نقشه راه فازبندی‌شده اجرای فیزیکی
"""
final_report = model.generate_content(final_prompt).text

# فاز ۵: ذخیره در فایل و به‌روزرسانی حافظه برداری برای آینده
report_filename = "APEX_BLUEPRINT.md"
with open(report_filename, "w", encoding="utf-8") as f:
f.write(final_report)

# افزودن به حافظه پایدار ریپازیتوری
memory.add(
documents=[f"Problem: {problem} | Key Innovation: {final_report[:500]}"],
metadatas=[{"score": score}],
ids=[f"run_{os.environ.get('GITHUB_RUN_ID', 'local_test')}"]
)

print(f"\n[✓] پایان موفق! گزارش در {report_filename} ثبت شد و در حافظه ذخیره گردید.")

if __name__ == "__main__":
main()
