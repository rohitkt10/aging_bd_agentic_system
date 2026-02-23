from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, SystemMessage
from pdb import set_trace 


# set up LLM
project_id = "jax-li-elr33-dev"
location = "us-central1"
model = "gemini-3-flash-preview"
temperature = 0.6
max_tokens = 1000
llm = ChatVertexAI(
            project=project_id,
            location=location,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# Basic invoke
message = "what day is it"
res = llm.invoke(message)
print(res.content)

# Structured invoke
schema = {
    "title": "status_response",
    "type": "object",
    "properties": {"day": {"type": "string"}},
    "required": ["day"]
        }

system_prompt="Return a JSON object with a status field."
llm_structured = llm.with_structured_output(schema)
messages = [
    SystemMessage(content=system_prompt),
    HumanMessage(content=f"Return status with answer to - {message}"),
            ]
response = llm_structured.invoke(messages)
print(response)
set_trace()
    
