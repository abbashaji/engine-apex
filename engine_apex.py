import os
import sys
import re
import json
import subprocess
import traceback
from duckduckgo_search import DDGS
import chromadb
import google.generativeai as genai

# ۱. پیکربندی کلید API و ارتباط با جمینای
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
print("[!] خطا: GEMINI_API_KEY در GitHub Secrets تعریف نشده است.")
sys.exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(
"gemini-1.5-flash",
generation_config={"temperature": 0.4}
)
radical_model = genai.GenerativeModel(
"gemini-1.5-flash",
generation_config={"temperature": 0.8}
)

# ۲. جستجوی زنده وب
def search_web(query, max_results=4):
print(f"[🔍] در حال کاوش زنده وب برای: {query}...")
try:
results = DDGS().text(query, max_results=max_results)
if not results:
return "داده‌ای در وب یافت نشد."
return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
except Exception as e:
return f"عدم امکان جستجو: {str(e)}"

# ۳. حافظه برداری محلی (ChromaDB)
def setup_memory():
client = chromadb.PersistentClient(path="./.vector_memory")
collection = client.get_or_create_collection(name="apex_knowledge")
return collection

def query_memory(collection, text, n_results=2):
try:
count = collection.count()
if count == 0:
return "حافظه قبلی خالی است (اولین اجرا)."
res = collection.query(query_texts=[text], n_results=min(n_results, count))
return "\n".join(res['documents'][0]) if res['documents'] else "یافته‌ای نبود."
except Exception:
return "خطا در بازیابی از حافظه برداری."

# ۴. جعبه‌شنی اجرای کد (Execution Sandbox)
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
return False, "توقف اجرا: زمان بیش از حد مجاز (Timeout)."
except Exception as e:
if os.path.exists(test_file):
os.remove(test_file)
return False, str(e)

# ۵. استخراج کد با Regex بدون باگ استرینگ
def extract_code_block(text):
match = re.search(r"
```(?:python)?\s*(.*?)\s*
```", text, re.DOTALL)
if match:
return match.group(1).strip()
return ""

def main():
if not os.path.exists("problem.txt"):
print("[!] فایل problem.txt یافت نشد.")
return

with open("problem.txt", "r", encoding="utf-8") as f:
problem = f.read().strip()

print(f"\n[🚀] شروع چرخه سرحد مطلق برای مسئله:\n>>> {problem}\n")

# فاز ۱: حافظه
memory = setup_memory()
past_learnings = query_memory(memory, problem)

# فاز ۲: کاوش وب
search_prompt = f"Produce a compact 3-word web search query to find recent technological or scientific breakthroughs about: {problem}. Return ONLY the query."
sq = model.generate_content(search_prompt).text.strip().replace('"', '').replace('\n', '')
web_data = search_web(sq)

# فاز ۳: چرخه تکاملی خوداصلاح‌گر
iteration = 1
max_iterations = 3
converged = False
current_solution = ""
critique_history = []

while iteration <= max_iterations and not converged:
print(f"\n═══════════════════════════════════════════════")
print(f"[*] دور تکاملی {iteration}/{max_iterations}")
print(f"═══════════════════════════════════════════════")

radical_prompt = (
"You are AGENT ALPHA (Radical Transmorphic Architect).\n"
f"Problem: {problem}\n"
f"Past Insights: {past_learnings}\n"
f"Web Grounding: {web_data}\n"
f"Previous Feedback: {json.dumps(critique_history, ensure_ascii=False)}\n\n"
"TASK:\n"
"1. Synthesize a radical, high-order, non-obvious solution.\n"
"2. Provide a self-contained Python script inside standard python code fences that models or tests the mathematical/computational core of this solution.\n"
)
alpha_res = radical_model.generate_content(radical_prompt).text

# استخراج و آزمایش کد
code_block = extract_code_block(alpha_res)
code_report = "بدون کد ارائه‌شده."
if code_block:
print("[⚙️] اجرای شبیه‌سازی و تست کد در محیط سیستم‌عامل...")
success, output = run_python_code(code_block)
if success:
code_report = f"موفقیت‌آمیز:\n{output}"
print(f"[✓] خروجی شبیه‌سازی:\n{output}")
else:
code_report = f"خطا در اعتبارسنجی فرضیه:\n{output}"
print(f"[✗] خطای محاسباتی:\n{output}")

# نقد بدبینانه
beta_prompt = (
"You are AGENT BETA (Nihilistic Adversary).\n"
f"Problem: {problem}\n"
f"Proposed Solution: {alpha_res}\n"
f"Code Sandbox Results: {code_report}\n\n"
"TASK:\n"
"Brutally dismantle this idea. Expose all operational bottlenecks, thermodynamic impossibilities, and economic flaws.\n"
"Rate it from 0 to 100.\n"
"Format:\nSCORE: <number>\nCRITIQUE: <ruthless critique>"
)
beta_res = model.generate_content(beta_prompt).text

score = 70
for line in beta_res.split("\n"):
if "SCORE:" in line:
digits = re.findall(r"\d+", line)
if digits:
score = int(digits[0])
break

print(f"[📊] نمره پایداری در دور {iteration}: {score}/100")

if score >= 90 or iteration == max_iterations:
converged = True
current_solution = alpha_res
critique_history.append({"iteration": iteration, "score": score, "critique": beta_res, "code_status": code_report})
print("[★] سیستم به سطح پایداری و بلوغ رسید.")
break
else:
critique_history.append({"iteration": iteration, "score": score, "critique": beta_res, "code_status": code_report})
iteration += 1

# فاز ۴: سنتز معماری نهایی
print("\n[*] در حال تدوین نقشه راه نهایی (Dialectical Blueprint)...")
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
final_report = model.generate_content(final_prompt).text

# فاز ۵: ثبت در فایل و پایگاه دانش برداری
with open("APEX_BLUEPRINT.md", "w", encoding="utf-8") as f:
f.write(final_report)

try:
run_id = os.environ.get("GITHUB_RUN_ID", "local")
memory.add(
documents=[f"Problem: {problem} | Key Insights: {final_report[:600]}"],
metadatas=[{"score": score}],
ids=[f"run_{run_id}"]
)
except Exception as e:
print(f"[!] نادیده گرفتن خطای جزئی ذخیره برداری: {e}")

print("\n[✓] عملیات با موفقیت به پایان رسید. سند APEX_BLUEPRINT.md ایجاد شد.")

if __name__ == "__main__":
main()
