from dotenv import load_dotenv
load_dotenv()
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List
from repo2readme.llm.factory import create_llm


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def truncate_text(text: str, max_tokens: int) -> str:
    """Hard-caps a single string to fit within max_tokens (pure string slicing, no API calls)."""
    if not text:
        return text
    char_limit = max_tokens * 4
    if len(text) > char_limit:
        return text[:char_limit] + "\n...(truncated)"
    return text


def summary_to_text(item) -> str:
    """Converts a summary item to plain text, whether it's a string or a dict."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("summary", "content", "text"):
            if key in item and isinstance(item[key], str):
                return item[key]
        return str(item)
    return str(item)


def truncate_summaries(summaries: List, max_tokens: int) -> str:
    """Combines and hard-caps the summaries list to fit within max_tokens."""
    text_items = [summary_to_text(s) for s in summaries]
    combined = "\n".join(text_items)
    return truncate_text(combined, max_tokens)


def generate_readme(summaries:List[str],tree_structure:str,feedback:List[str],latest_readme:str,provider:str, model_name:str, base_url:str):
    model = create_llm(
    provider= provider or "groq",
    model= model_name or "openai/gpt-oss-120b",
    base_url=base_url
)
    prompt = PromptTemplate(
    template="""
You are an expert README Generator and a Markdown file Specialist.
Your task is to generate a cleaned, well-structured, professinal README.md.
Rules:
- Do NOT hallucinate.
- Do NOT invent any features, files, tech stack, on your own
- If anypart do NOT have the efficient data avoid that part (do NOT write placeholders).
- Do not add any wrong information, broken links
---
**Repository Structure**
{tree_structure}
** File Summaries **  
{summaries}
Previous Readme file:
{latest_readme}
Previous reviewer feedback (if any):
{feedback}
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
- Ensure the README is production-ready.
- After reading the README file any one must understand all about project.
- Use simple, human-friendly language.
- Do NOT include images, SVGs, logos, or badges unless a VALID HTTPS image URL is explicitly known.
- Prefer plain text lists over icons if unsure.
- Emojis are allowed ONLY in the Table of Contents, NOT in section headings.
- Section headings MUST NOT contain emojis.
- Table of Contents links MUST exactly match the section headings.
- Do NOT generate broken links, placeholder images, or empty image tags.
- If unsure about icons or badges, OMIT them completely.
- Markdown must render correctly on GitHub.
---
** Now Generate the final README.md **
Return ONLY valid Markdown
""",
    input_variables=["summaries", "tree_structure","latest_readme","feedback"]
)
    parser=StrOutputParser()
    chain=prompt|model| parser

    # Hard-cap EVERY piece that goes into the final prompt (not just summaries),
    # since the existing README, tree structure, and feedback can also be large.
    final_summaries = truncate_summaries(summaries, max_tokens=2000)
    tree_structure = truncate_text(tree_structure, max_tokens=500)
    latest_readme = truncate_text(latest_readme, max_tokens=500)

    if feedback:
        feedback = "\n".join(truncate_text(summary_to_text(f), max_tokens=60) for f in feedback[:3])
    else:
        feedback = ""

    response=chain.invoke({ 
        "summaries": final_summaries,
        "tree_structure": tree_structure,
        "latest_readme":latest_readme,
        "feedback": feedback
        })
    return response