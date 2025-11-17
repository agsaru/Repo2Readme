from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tree import extract_tree
def readme_builder():
    model =ChatGroq (
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        
    )
    prompt=PromptTemplate(
    template="generate readme fle using the summaries of the files {summaries}",
    input_variables=["summaries"]
    )
    parser=StrOutputParser()
    chain=prompt|model| parser
    return chain
def generate_readme(summaries):
    chain=readme_builder()
    return chain.invoke({"summaries":summaries})






