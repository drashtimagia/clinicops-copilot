import json
import os
from copy import deepcopy

from ai_pipeline.config import config
from ai_pipeline.data_ingestion.parser import MarkdownParser
from ai_pipeline.data_ingestion.ingest import process_directory, MANUALS_DIR, SOPS_DIR
from ai_pipeline.retrieval.service import RetrievalService
from ai_pipeline.memory.matcher import MemoryMatcher
from ai_pipeline.memory.loader import IncidentLoader
from ai_pipeline.engine.generator import get_decision_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTCOMES_PATH = os.path.join(BASE_DIR, 'data', 'expected_outcomes.json')

def load_all_chunks():
    parser = MarkdownParser()
    chunks = []
    chunks.extend(process_directory(MANUALS_DIR, "manual", parser))
    chunks.extend(process_directory(SOPS_DIR, "sop", parser))
    return chunks

def main():
    print("=========================================")
    print(" ClinicOps Copilot - MVP Evaluation ")
    print("=========================================\n")

    # 1. Setup Retrieval Data
    chunks = load_all_chunks()
    if not chunks:
        print("Error: No document chunks available.")
        return
        
    with open(OUTCOMES_PATH, 'r') as f:
        expected_outcomes = json.load(f)

    # 2. Setup Pipeline Services
    retrieval_service = RetrievalService(chunks)
    memory_matcher = MemoryMatcher()
    engine = get_decision_engine()
    
    # Load chronological incidents array
    all_incidents = IncidentLoader.load_all()
    
    # 3. Force Memory to empty at start to simulate chronological processing
    memory_matcher.past_incidents = []
    
    total = len(all_incidents)
    correct_escalations = 0
    retrieval_hits = 0
    
    print(f"Evaluating {total} incidents chronologically to test Memory...\n")
    print("-" * 90)
    print(f"{'ID':<10} | {'Retrieve':<8} | {'Escalate Match':<16} | {'Mem Flag':<8} | Note")
    print("-" * 90)

    for inc in all_incidents:
        inc_id = inc.id
        description = inc.description
        device = inc.device
        text = f"Device: {device}\nDescription: {description}"
        expected = expected_outcomes.get(inc_id, {})
        
        # A. Pipeline Stage 1: Retrieval
        retrieved_chunks = retrieval_service.search(text, top_k=3)
        
        # B. Pipeline Stage 2: Memory (before this incident is added to history)
        memory_result = memory_matcher.analyze_incident(text)
        
        # C. Pipeline Stage 3: Decision Engine
        decision = engine.evaluate_incident(text, inc_id, retrieved_chunks, memory_result)
        
        # D. Add to memory history for the NEXT incident's context
        memory_matcher.past_incidents.append(inc)
        
        # Metrics logic
        has_citations = len(decision.citations) > 0
        if has_citations:
            retrieval_hits += 1
            
        exp_escalate = expected.get("expected_escalate", False)
        escalate_match = decision.escalate == exp_escalate
        if escalate_match:
            correct_escalations += 1
            
        # Output table row
        c_status = "Pass" if has_citations else "Fail"
        e_status = "Pass" if escalate_match else "Fail"
        m_status = "Yes" if decision.memory_match else "No"
        
        note = "OK" if e_status == "Pass" else f"Expected escalate={exp_escalate}, got {decision.escalate}"
        print(f"{inc_id:<10} | {c_status:<8} | {e_status:<16} | {m_status:<8} | {note}")

    print("-" * 90)
    print("\n--- SCORECARD ---")
    print(f"Total Incidents Evaluated: {total}")
    print(f"Retrieval Hit Rate:        {retrieval_hits}/{total} ({(retrieval_hits/total)*100:.0f}%)")
    print(f"Escalation Accuracy:       {correct_escalations}/{total} ({(correct_escalations/total)*100:.0f}%)")

if __name__ == "__main__":
    main()
