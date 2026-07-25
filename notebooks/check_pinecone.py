from dotenv import load_dotenv
import os
from pinecone import Pinecone

load_dotenv()  # reads .env from the current working directory

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

print("Indexes found:")
for idx in pc.list_indexes():
    print(f"  {idx['name']} — dim={idx['dimension']}, metric={idx['metric']}")