from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel,Field,field_validator
from typing import List, Dict, Any, Optional,Union

class FunctionSummary(BaseModel):
    name:str=Field(...,description="The name of the function or the class")
    description:str=Field(...,description="One-line summary of what the function/class has done")
    params:Optional[Union[List[str], Dict[str, Any]]] =Field(default=None,description="List of parameters name")
    returns:Optional[str]=Field(default=None,description="What it returns as a output")
    
    @field_validator("params")
    def normalize_params(cls, value):
        if value is None:
            return None
        if isinstance(value, dict):
            # Convert dict to list
            return [f"{k}={v}" for k, v in value.items()]
        if isinstance(value, list):
            return value
        raise ValueError("params must be a list or dict")



class CodeSummary(BaseModel):
    file_path:str
    language:str=Field(...,description="Programing language used")
    short_description:str =Field(...,description="short summary of the code ")
    functions:List[FunctionSummary]=Field(default_factory=list,description="Details of the function or class")
    imports:Optional[List[str]]=Field(default=None,description="Imported libraries or  modules or classes or functions")
    exports:Optional[List[str]]=Field(default=None,description="Exported libraries or  modules or classes or functions")
    
    @field_validator('short_description')
    def validate_short_description(cls, value):
      if not value or not value.strip():
        raise ValueError("short_description must be non-empty")
      return value
    

parser=PydanticOutputParser(pydantic_object=CodeSummary)