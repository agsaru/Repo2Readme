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
You are an expert README Generator and a Markdown file Specialist.
Your task is to generate a cleaned, well-structured, professinal README.md.

Rules:
- Do NOT hallucinate.
- Do NOT invent any features, files, tech stack, on your own
- If anypart do NOT have the efficient data avoid that part (do NOT write placeholders).
---

**Repository Structure**
{tree_structure}

** File Summaries **  
{summaries}


---

## README.md Requirements
Generate a high-quality Github ready README.md file ** ONLY from the provided File Summaries.

The README.md file may include these sections IF APPLICABLE (I mean IF AVAILABLE in the provided data):
1. **Project Title**
2. **Short Description**
(2–4 clear human-friendly lines)
3. **Table of Contents**
4. **Tech Stack**
(with emojis/icons; include ONLY technologies actually found in summaries or file paths)
5. **Key Features**
6. **Folder Structure**
(Use EXACTLY the provided tree structure)
7. **Installation Instructions**
8. **Usage Examples** 
9. **Configuration / Environment Variables**  
  (include ONLY if explicitly mentioned in any file summary)
10. **API Endpoints**  
(include ONLY if server/backend routes appear in summaries)
11. **How the Code Works**  
    (summarize using ALL file summaries)
12. **Contributing Guidelines**
13. **License**
14. **Credits / Acknowledgements**

You can add other sections if you think needed to add.
And You can also change the sections name as per the summaries.
---
** Additional Instructions **
- Keep the README clean, well-structured, and professional.
- Use emojis only where appropriate.
- Ensure the README is production-ready.
- After reading the README file any one must understand all about project.
- Use simple, human-friendly language.
---
** Now Generate the final README.md **
Return ONLY valid Markdown


""",
    input_variables=["summaries", "tree_structure"]
)


    parser=StrOutputParser()
    chain=prompt|model| parser
    return chain
def generate_readme(summaries,tree_structure):
    chain=readme_builder()
    return chain.invoke({"summaries":summaries,"tree_structure":tree_structure})






