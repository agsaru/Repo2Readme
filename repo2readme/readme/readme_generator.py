# from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

def readme_builder():
    
    api_key = os.getenv("GOOGLE_API_KEY")
    model=ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
    prompt = PromptTemplate(
    template="""
You are an expert technical writer and a senior software engineer.

Your task is to generate a clean, polished, and professional **README.md** for this repository using the information provided below.

---

### 📁 Repository Structure
{tree_structure}

### 📄 File Summaries
{summaries}

### 📂 All File Paths
{file_paths}

---

### ✅ What the README Must Include if only they are available dont make these sections if they are not available

1. **Project Title**
2. **Short Description** (2–4 clear, human-friendly lines)
3. **Table of Contents**
4. **Tech Stack (with icons/emojis)** — ONLY for technologies actually present in the provided summaries/tree.
5. **Key Features**
6. **Folder Structure** (use the exact provided tree)
7. **Installation Instructions** (simple and readable)
8. **Usage Examples** (with code blocks where needed)
9. **Configuration / Environment Variables** (only if included in repo)
10. **API Endpoints** (only if backend/server files exist)
11. **How the Code Works** — summarize using *every* provided file summary
12. **Contributing Guidelines**
13. **License**
14. **Credits / Acknowledgements**

---

### 📝 Requirements

- Use clean and readable Markdown formatting.
- Be beginner-friendly but professional.
- Do **NOT** invent any files, folders, APIs, or concepts not explicitly provided.
- Make minimal, reasonable assumptions only when absolutely necessary.
- Ensure all explanations come directly from the repository summaries.
- The README must be complete, self-contained, and GitHub-ready.
- Use emojis/icons ONLY where appropriate (especially in Tech Stack, Features, and TOC).
- Maintain a friendly, clear tone.

---

### 🚀 Now generate the README.md:
""",
    input_variables=["summaries", "tree_structure", "file_paths"]
)


    parser=StrOutputParser()
    chain=prompt|model| parser
    return chain
def generate_readme(summaries,tree_structure,file_paths):
    chain=readme_builder()
    return chain.invoke({"summaries":summaries,"tree_structure":tree_structure,"file_paths":file_paths})






