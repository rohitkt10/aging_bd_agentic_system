from pdb import set_trace

import requests

query = "SIRT1"
query = "DNA repair mitochondrial"
query = "mitochondrial, DNA repair"
# query = "GHR, SIRT1, IGF1R"
response = requests.get(
    "https://open-genes.com/api/gene/search",
    params={"bySuggestions": query, "pageSize": 20},
)
res = response.json()
options = res["options"]
items = res["items"]


print(items[0].keys())

print()
print([item["symbol"] for item in items])

print([item["commentCause"] for item in items])
set_trace()
