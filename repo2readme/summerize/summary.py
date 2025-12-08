from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import os
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()


def create_summarizer(file_path: str, language: str, content: str):
    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2, 
    )
    parser=JsonOutputParser()
    prompt = PromptTemplate(
        template="""
You are an expert code analyst.
Your task is generate a summary of the code that summary will help later to 
generate a README.md file. 
The code file can be in any programming language.So be careful about with which
file type are you dealing with. 

Rules:
- Do not hallucinate about the code.
- Do not rewrite the code.
- Do not lose the meaning of the code file.
- Do not guess missing information.


Your summary MUST include:
- File path 
{file_path}
- Purpose of the code in the file
- If the line of code is less the summary will be short
and the if the line of code is high the summary will be large.
- The summary size will depend on the total line of codes
- Add key functions, classes,what is the perpose of them
- Important logic and algorithms
- All the dependencies and intregrations with other files
- Any configuration, environment varilables, or API usage
- Also add the information if the code has any important portions

Your returned JSON MUST contain at least:
Your returned JSON MUST contain at least:
{{
  "file_path": "{file_path}",
  "description": ""
}}

You MUST return a valid JSON object.
Add other fields to the JSON ONLY if they are present in the code.

Now summarize this code:

File Path: {file_path}
Language: {language}

Code:
{content}
Return ONLY JSON.  
{format_instructions}
    """,
    input_variables=["file_path", "language", "content"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

    chain = prompt | model | parser
    return chain


def summarize_file(file_path: str, language: str, content: str):
    try:
        chain = create_summarizer(file_path, language, content)
        return chain.invoke({
            "file_path": file_path.replace("\\", "/"),
            "language": language,
            "content": content
        })
    except Exception as e:
        print(file_path)
        print("SUMMARY ERROR:", e)
        return {"file_path": file_path, "error": str(e)}
