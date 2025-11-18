from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from .schema import parser
from dotenv import load_dotenv
import os
load_dotenv()

def create_summarizer(file_path: str, language: str, text: str):
    model =ChatGroq (
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        
    )
    prompt = PromptTemplate(
    template=r"""
You are a senior software engineer. Your task is to read the given source code file and produce an accurate, concise JSON summary.

Your output MUST follow **exactly** the formatting rules below:
{format_instructions}

CRITICAL RULES — Read Carefully
- Output **only valid JSON**, nothing else.
- **Do NOT output the schema** or describe it.
- **Do NOT output markdown, comments, or explanations**.
- Every field must strictly match the structure required by the format instructions.
- Never hallucinate functions, params, returns, imports, or exports.
- Only include information that is explicitly present in the file.
- File paths must use `/` forward slashes.
- Do NOT wrap JSON in backticks.
- Do NOT add a prefix or suffix before or after the JSON.



 What you must extract from the code:
- High-level purpose of the file (`short_description`)
- All functions, methods, or classes
- Parameters each function accepts
- Return values
- Imports used
- Exports (JS/TS)
- Any configuration or model/schema definitions

 How to summarize functions:
- `name`: exact function/method/class name as written in code
- `description`: one short sentence describing what it does
- `params` (choose the best fit based on code):
    - a list of parameter names
    - OR a JSON object describing parameter → type/value
    - OR null if no parameters
- `returns`:
    - a short string description
    - OR a JSON structure
    - OR null

✔ If a function returns an object, you may outline its keys.  
✔ If the return type is unclear, use a short textual summary.  
✔ Do NOT invent missing types or values.

----

Below is the actual file content you must summarize:
---- FILE CONTENT START ----
{content}
---- FILE CONTENT END ----
""",
    input_variables=["file_path", "language", "content"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)



    chain = prompt | model | parser
    return chain

def summarize_file(file_path: str, language: str, content: str):
    chain = create_summarizer(file_path, language, content)
    summary=chain.invoke({
        "file_path":file_path.replace("\\", "/"),
        "language":language,
        "content": content.replace("\\", "/")})
    return summary


