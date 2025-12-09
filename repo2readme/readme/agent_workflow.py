from langgraph.graph import StateGraph,START,END
from typing import TypedDict,List,Annotated
import operator
from repo2readme.readme.readme_generator import generate_readme
from repo2readme.readme.reviewer_agent import readme_reviewer
class ReadmeState(TypedDict):
    summaries:List[str]
    tree_structure:str
    readme:Annotated[list[str],operator.add]
    score:Annotated[list[float],operator.add]
    feedback:Annotated[list[str],operator.add]
    best_readme:str
    best_score:float
    iteration_no:int
    max_iterations:int

def generate_readme_node(state:ReadmeState):
    readme=generate_readme(
       summaries=state['summaries'],
       tree_structure=state['tree_structure'],
       feedback=state['feedback']
    )
    return {
        'readme':[readme]
    }
def readme_reviewer_node(state:ReadmeState):
    latest_readme=state['readme'][-1]
    review=readme_reviewer(latest_readme)
    best_score=state['best_score']
    best_readme=state['best_readme']
    if review.score>best_score:
        best_score=review.score
        best_readme=latest_readme

    return {
        'score':[review.score],
        'feedback':[review.feedback],
        'iteration_no':state['iteration_no']+1,
        'best_score':best_score,
        'best_readme':best_readme
        }

def readme_condition(state:ReadmeState):
    score=state['score'][-1]
    max_iterations=state['max_iterations']
    iteration=state['iteration_no']
    if score>=9.0 or iteration>=max_iterations:
        return END
    else:
        return 'generate_readme'


graph=StateGraph(ReadmeState)
graph.add_node('generate_readme',generate_readme_node)
graph.add_node('readme_reviewer',readme_reviewer_node)

graph.add_edge(START,'generate_readme')
graph.add_edge('generate_readme','readme_reviewer')
graph.add_conditional_edges('readme_reviewer',readme_condition,{END:END,"generate_readme": "generate_readme"})

workflow=graph.compile()
