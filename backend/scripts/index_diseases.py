import os
import sys

# Stealth Fix: "Hide" broken TensorFlow from libraries
sys.modules['tensorflow'] = None

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import time
import torch

# Add backend to path so we can import config
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    from config import settings
    from utils.embeddings import embedder
    from pinecone import Pinecone, ServerlessSpec
except Exception as e:
    print(f"Error importing dependencies: {e}")
    sys.exit(1)

# Constants
CSV_FILE = "Final_Augmented_dataset_Diseases_and_Symptoms.csv"
INDEX_NAME = settings.PINECONE_INDEX_DISEASES
BATCH_SIZE = 100
MAX_DISEASES = 500  # Set limit for fast demo "training"

def index_dataset():
    print(f"Loading dataset: {CSV_FILE}")
    if not os.path.exists(CSV_FILE):
        # Try finding it in parent dir if needed
        CSV_FILE_ALT = os.path.join(str(Path(__file__).resolve().parent.parent), CSV_FILE)
        if os.path.exists(CSV_FILE_ALT):
            FILENAME = CSV_FILE_ALT
        else:
            print(f"Error: {CSV_FILE} not found.")
            return
    else:
        FILENAME = CSV_FILE

    # Initialize Pinecone
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    
    # Check if index exists
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone Index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric='cosine',
            spec=ServerlessSpec(cloud='aws', region='us-east-1')
        )
    
    index = pc.Index(INDEX_NAME)

    # Process CSV
    print("Aggregating diseases and symptoms (this may take a minute)...")
    
    df_headers = pd.read_csv(FILENAME, nrows=0)
    symptom_cols = [c for c in df_headers.columns if c != 'diseases']
    
    disease_map = {}
    
    chunk_size = 20000
    for chunk in pd.read_csv(FILENAME, chunksize=chunk_size):
        for _, row in chunk.iterrows():
            disease = str(row['diseases']).strip()
            if disease not in disease_map:
                disease_map[disease] = set()
            
            for sym in symptom_cols:
                if row[sym] == 1:
                    disease_map[disease].add(sym.replace('_', ' '))

    print(f"Found {len(disease_map)} unique diseases.")
    
    print("Embedding and uploading to Pinecone...")
    vectors = []
    
    count = 0
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for disease, symptoms in tqdm(disease_map.items(), ascii=True, desc="Indexing"):
        if not symptoms:
            continue
            
        symptoms_list = sorted(list(symptoms))
        text = f"Medical Fact: {disease.capitalize()} is a condition characterized by symptoms such as {', '.join(symptoms_list)}."
        
        try:
            embedding = loop.run_until_complete(embedder.encode(text))
            
            vectors.append({
                "id": f"disease_{count}",
                "values": embedding,
                "metadata": {
                    "text": text,
                    "disease": disease,
                    "type": "medical_knowledge"
                }
            })
            
            count += 1
            
            if count >= MAX_DISEASES:
                print(f"Reached limit of {MAX_DISEASES} diseases for demo training.")
                break

            if len(vectors) >= BATCH_SIZE:
                index.upsert(vectors=vectors)
                vectors = []
        except Exception as e:
            print(f"Error processing {disease}: {e}")

    if vectors:
        index.upsert(vectors=vectors)
        
    print(f"Finished! Indexed {count} diseases successfully.")

if __name__ == "__main__":
    index_dataset()
