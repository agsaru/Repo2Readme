from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from .schema import parser
from dotenv import load_dotenv
import os

load_dotenv()


def create_summarizer(file_path: str, language: str, text: str):
    model = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2, 
    )

    prompt = PromptTemplate(
    template=r"""
You are a senior software engineer. Read the source code and generate a JSON summary matching the required schema.

{format_instructions}

================ RULES ================
- Output ONLY valid JSON.
- Do NOT add explanations, commentary, or markdown.
- Do NOT output the schema itself.
- Do NOT wrap the JSON in backticks.
- Do NOT hallucinate fields or values.
- Use forward slashes `/` for all paths.
- Follow the schema EXACTLY.

================ WHAT TO EXTRACT ================
- short_description: one sentence about the file.
- functions: all functions/classes/methods/components.
- params: parameter names or structured parameter objects.
- returns: text or object, or null.
- imports: modules/libraries used.
- exports: exported symbols.

================ PARAM RULES ================
- If code shows parameter names only → return a list of names.
- If code contains structured parameters → return a list of objects.
- If no parameters → return null.

================ FILE CONTENT ================
{content}
""",
    input_variables=["file_path", "language", "content"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

    chain = prompt | model | parser
    return chain


def summarize_file(file_path: str, language: str, content: str):
    chain = create_summarizer(file_path, language, content)
    summary = chain.invoke({
        "file_path": file_path.replace("\\", "/"),
        "language": language,
        "content": content.replace("\\", "/")
    })
    return summary
