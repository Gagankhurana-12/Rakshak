# 🛡️ Rakshak AI: Chief Medical Officer in Your Pocket

**Rakshak AI** is a next-generation, high-performance medical diagnostic platform. It doesn't just "chat"—it performs deep clinical correlation by bridging the gap between your real-time biometrics, your private medical history, and global scientific knowledge.

---

## 🚀 The Vision
Most health apps show you graphs; Rakshak AI tells you what they *mean*. By integrating **Google Fit** vitals with an advanced **Hybrid RAG (Retrieval-Augmented Generation)** system, Rakshak provides personalized, authoritative health insights that standard LLMs cannot reach.

---

## 🛠️ The Powerhouse (Tech Stack)
- **Engine**: FastAPI (Python 3.10) optimized for Windows stability.
- **LLM**: Groq (Llama 3.3 70B) for near-instant "Chief Medical Officer" reasoning.
- **Biometrics**: Google Fit API (REST).
- **Hybrid Memory**:
   - **Pinecone (Cloud, Single Index + Namespaces)**:
      - `default`: Global medical knowledge base (disease mappings).
      - `user_docs`: Private user medical document chunks.
      - `user_vitals`: Weekly/daily vitals history summaries.
- **Database**: PostgreSQL (Structured User Data).
- **Vision**: Tesseract OCR (Medical Report Processing).
- **Frontend**: React (Vite) with a premium health-tech aesthetic.

---

## 🔄 The Master Workflows

### 1. The Pulse Sync (Biometric Integration)
- **Auth**: Secure Google OAuth2 handshake with 100% reliable token persistence.
- **Alignment**: Every data point is auto-aligned to **IST (GMT+5:30)**, ensuring "Today's Steps" reset at local midnight.
- **Fallback**: Intelligent "Dummy Sleep" generation for users with missing Fit sessions, ensuring no gaps in analysis.

### 2. The Medical Memory (Document Ingestion)
- **Vision**: OCR scans images/PDFs of your medical reports.
- **Privacy**: Text is chunked and stored in Pinecone `user_docs` namespace, filtered by `user_id` during retrieval.

### 3. The CMO Diagnostic (AI Analysis)
When you ask a question, Rakshak performs a **Triple-Context Search**:
1.  **Context A**: Current Vitals (Heart Rate, Steps, Sleep trends).
2.  **Context B**: Your Medical History (Searching Pinecone `user_docs` namespace).
3.  **Context C**: Global Facts (Searching Pinecone `default` namespace for disease signatures).

**The Result**: The "Chief Medical Officer" prompt correlates all three to give a differential diagnosis, not just a generic suggestion.

---

## ✨ Key Features
- **Differential Reasoning**: AI identifies biometric anomalies (e.g., "Pulse is 15% higher than your baseline") and links them to symptoms.
- **Zero-Crash Windows Backend**: Custom Proactor loop policies ensure 100% uptime on Windows environments.
- **Security-First**: Comprehensive `.gitignore` protocol prevents API keys and large datasets from ever reaching GitHub.
- **High-Speed Indexing**: Specialized scripts allow for rapid "training" of the AI on massive medical datasets.

---

## 🛠️ Getting Started

### Local Setup
1. **Clone the Repo**
2. **Backend**:
   - `pip install -r requirements.txt`
   - Set up your `.env` (Google Client ID, Groq API Key, Pinecone API Key).
   - `python main.py`
3. **Frontend**:
   - `npm install`
   - `npm run dev`

### AI Training
To populate the medical knowledge base:
```bash
python scripts/index_diseases.py
```

---

## 🏆 Hackathon Spotlight
Rakshak AI solves the **"Generic LLM Problem"** in healthcare by giving the model "eyes" into the user's actual body (Google Fit) and "memory" of their past tests (Pinecone user namespaces). It represents a stable, production-ready implementation of AI-driven personalized medicine.
