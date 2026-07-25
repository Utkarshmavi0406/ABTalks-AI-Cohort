# Vector Database Notes — Chroma vs Pinecone

## Comparison

| Dimension | Chroma | Pinecone |
|---|---|---|
| **Deployment** | Local, embedded — runs in-process, persists to disk (`chroma_data/`) via `PersistentClient` | Fully managed cloud service — no local process, accessed via API over the network |
| **Free-tier limits** | No limits at all — it's just a local library, storage capped only by your own disk | Free/Starter tier caps on index count, storage, and read/write units (varies by plan; check current limits on Pinecone's pricing page since these change) |
| **Latency** | Very low — queries run in-process on the same machine, no network round-trip | Higher — every query is a network call to Pinecone's servers, so latency depends on your connection and their region |
| **Ease of setup** | `pip install chromadb`, then a few lines of Python — no account, no signup, working in under a minute | Requires account signup, dashboard index creation (name, dimensions, metric, cloud/region), and API key management before the first query |
| **Enterprise access control (per-member / per-plan)** | No built-in access control — you'd have to enforce it yourself in application code (e.g. filter query results by metadata like `plan_type` after retrieval, or run separate collections per tenant) | Offers namespaces to logically partition data (e.g. one namespace per plan or per member cohort) and supports metadata filtering at query time; still requires the application layer to enforce *who* can query *which* namespace, but the primitives for isolation are more built-in |

## Which one for this program

For this program, **Chroma** is the better choice going forward. It requires no signup, no API key management, and no network dependency — everything runs locally and is fully free with no usage caps to worry about, which matters for a learning project where I want to iterate quickly without hitting rate limits or quotas. Pinecone's managed infrastructure and namespace-based access control would matter more in a real production deployment serving actual members at scale, where per-plan or per-member data isolation and horizontal scaling become real requirements — but for building and testing the retrieval pipeline in this course, Chroma's simplicity and zero-friction local setup outweighs Pinecone's production-oriented features that aren't needed yet.