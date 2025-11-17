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
    template="""
You are a senior software engineer. Summarize this file carefully.

Return a JSON object strictly following this schema:
{format_instructions}
DO NOT return:
- $defs
- schema
- properties
- required
- explanations
- markdown
- text outside JSON
- comments
- anything EXTRA

Return ONLY the JSON.
Always convert file paths to use forward slashes `/` instead of backslashes `\`.

Path of the File 
{file_path}
Programming Language Used
{language}

---- FILE CONTENT START ----
{text}
---- FILE CONTENT END ----

Rules:
- DO NOT hallucinate code that is not present.
- Extract real functions, classes, imports, routes, configs, schemas.
- Keep 'short_description' very clear and concise.
- Always return valid JSON.
""",
    input_variables=["file_path", "language", "text"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

    chain = prompt | model | parser
    return chain

def summarize_file(file_path: str, language: str, text: str):
    chain = create_summarizer(file_path, language, text)
    summary=chain.invoke({"file_path":file_path,"language":language,"text":text})
    return summary


# python -m cli.main --url https://github.com/agsaru/url-shortner.git