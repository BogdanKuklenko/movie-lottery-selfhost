import requests

resp = requests.post(
    "http://localhost:8888/api/fetch-movie",
    json={"query": "Интерстеллар"}
)
data = resp.json()
print(f"Ответ: {data}")
if 'poster' in data:
    print(f"\nURL постера: {data['poster']}")

