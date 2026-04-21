# 🚀 RAG Application using Ollama and ShakthiDB

A Retrieval-Augmented Generation (RAG) application that combines local LLMs using Ollama with a vector database (ShakthiDB) to generate accurate and context-aware responses.

---

## 📌 Overview

This project implements a RAG pipeline where:
- User queries are processed
- Relevant data is retrieved from a vector database
- A local LLM generates responses using retrieved context

---

## 🧠 What is RAG?

Retrieval-Augmented Generation (RAG) is a technique that combines:
- Information retrieval from a database
- Text generation using a language model

This improves accuracy and relevance of responses.

---

## ⚙️ Tech Stack

- Ollama (Local LLM)
- ShakthiDB (Vector Database)
- Python
- Embeddings Model

---

## 🏗️ Architecture

User Query  
↓  
Embedding Generation  
↓  
Vector Search (ShakthiDB)  
↓  
Retrieve Context  
↓  
Ollama LLM  
↓  
Final Response  

---

## 📂 Project Structure

RAG-Application/
│
├── app.py
├── embeddings.py
├── retriever.py
├── database/
├── utils/
├── requirements.txt
└── README.md

---

## 🚀 Installation

### 1. Clone the Repository
git clone https://github.com/veeresh8088-star/RAG-Application-using-Ollama-and-Shakthidb.git
cd RAG-Application-using-Ollama-and-Shakthidb

### 2. Install Dependencies
pip install -r requirements.txt

### 3. Install Ollama
Download from: https://ollama.com

Pull a model:
ollama pull llama3

---

## ▶️ Usage

Run the application:
python app.py

Then:
- Add your documents
- Ask questions
- Get AI-generated responses

---

## ✨ Features

- Runs locally (no API cost)
- Context-aware answers
- Fast vector search
- Privacy-friendly

---

## 🔥 Use Cases

- Document Question Answering
- Knowledge Base Chatbot
- Study Assistant
- Resume Analyzer

---

## 📊 Future Improvements

- Add UI (Streamlit/React)
- Chat history support
- Multi-document upload
- API deployment

---

## 🤝 Contributing

Contributions are welcome!

---

## 📜 License

MIT License

---

## 👨‍💻 Author

Veeresh  
GitHub: https://github.com/veeresh8088-star

---

## ⭐ Support

If you like this project, give it a ⭐ on GitHub!
