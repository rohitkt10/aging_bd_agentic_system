#!/usr/bin/env python3
"""Test OpenGenes API to understand what queries work."""

import requests
import json
import time 
from pdb import set_trace

def test_query(query: str, page_size: int = 20):
    """Test a query and return results."""
    response = requests.get(
        "https://open-genes.com/api/gene/search",
        params={"bySuggestions": query, "pageSize": page_size},
    )
    res = response.json()
    items = res.get("items", [])
    options = res.get("options", [])
    symbols = [item.get("symbol") for item in items]
    return {
        "query": query,
        "items_count": len(items),
        "options_count": len(options),
        "symbols": symbols[:10],  # First 10
    }

# Test different query types
queries = [
    # Gene symbols
    "SIRT1",
    "TP53",
    "FOXO3",

    # Multiple symbols
    "SIRT1, TP53",
    "FOXO3, mTOR",

    # Keywords/broad terms
    "inflammation",
    "mitochondrial",
    "DNA repair",
    "senescence",
    "autophagy",
    "telomere",
    "aging",

    # Combined
    "mitochondrial DNA",
    "DNA sensing",
    "innate immunity",

    # Partial matches
    "SIRT",
    "FOX",
    "mTOR",
]

queries = ["cGAS, STING", "cGAS"]

print("="*70)
print("OPENGENES API QUERY TESTING")
print("="*70)
working = []
not_working = []
for query in queries:
    time.sleep(1)
    result = test_query(query)
    print(f"\nQuery: '{query}'")
    print(f"  Items: {result['items_count']}, Options: {result['options_count']}")
    if result['symbols']:
        print(f"  Symbols: {result['symbols']}")
    else:
        print(f"  Symbols: []")
    if result['items_count'] > 0:
        working.append((query, result['items_count']))
    else:
        not_working.append(query)

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

print(f"\nWorking queries ({len(working)}):")
for q, count in working:
    print(f"  - '{q}': {count} results")

print(f"\nNot working queries ({len(not_working)}):")
for q in not_working:
    print(f"  - '{q}'")
