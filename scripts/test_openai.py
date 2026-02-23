#!/usr/bin/env python3
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pdb import set_trace

api_key = "sk-proj-UVzjOAPkIwVAe2LRqnBrKH6LaOpyoQFC"+\
    "BPLg2RX0D8M7nWV0n167ZbxaVH6JY-i3KPRmmlyYABT3BlbkFJab67"+\
    "-1JS898INeIVo3hiZmbtm1FV5uealfvqje5udynR0SytHRHHkkUHM"+\
    "_s3HGUvcenj2VJbQA"
llm = ChatOpenAI(
    api_key=api_key, 
    model="gpt-5-nano",
    max_tokens=8000,
    temperature=0.6,
    )

# Basic invoke
message = "what day is it"
res = llm.invoke([HumanMessage(content=message)])
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