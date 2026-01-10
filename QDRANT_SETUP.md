# Qdrant Setup Guide

## Installing Qdrant via Docker

Qdrant will run as a Docker container for the RAG (Retrieval-Augmented Generation) system.

### Prerequisites
- Docker Desktop installed and running

### Installation Steps

1. **Start Docker Desktop** (if not already running)

2. **Run Qdrant container:**
   ```bash
   docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
   ```

3. **Verify Qdrant is running:**
   ```bash
   curl http://localhost:6333/
   ```
   
   You should see a JSON response with Qdrant version info.

### Alternative: Manual Installation

If Docker is not available, you can run Qdrant locally:

```bash
# Download Qdrant binary
wget https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-x86_64-pc-windows-gnu.zip

# Extract and run
unzip qdrant-x86_64-pc-windows-gnu.zip
./qdrant.exe
```

### Testing Connection from Python

```python
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
print(client.get_collections())  # Should return empty list initially
```

### Next Steps
- Once Qdrant is running, proceed with Phase 4 (RAG & Curriculum Alignment)
- The system will create the `curriculum_standards` collection automatically
