import json
from ai_pipeline.memory.matcher import MemoryMatcher

def main():
    print("=========================================")
    print(" ClinicOps Copilot - Memory Evaluation ")
    print("=========================================\n")
    
    matcher = MemoryMatcher()
    
    test_cases = [
        {
            "name": "The 3rd Strike Monitor",
            "text": "Mobile vital signs monitor VPM5-9002 shut off in the hallway again. I put it on the dock last night."
        },
        {
            "name": "Identical Problem, Different Device",
            "text": "The other vital signs monitor VPM5-1044 shut off in the hallway."
        },
        {
            "name": "One-Off Issue",
            "text": "The autoclave hinge is squeaking loudly."
        },
        {
            "name": "Error Code Exact Match",
            "text": "Centrifuge threw an E-04 error again."
        }
    ]
    
    for case in test_cases:
        print(f"\n--- SCENARIO: {case['name']} ---")
        print(f"INPUT: {case['text']}")
        
        result = matcher.analyze_incident(case["text"])
        
        print(f"Bias Escalation: {result.bias_escalation}")
        print(f"Reasoning: {result.reasoning}")
        print(f"Matches Found: {len(result.similar_incidents)}")
        
        if result.similar_incidents:
            print("Match IDs: ", [i.id for i in result.similar_incidents])

if __name__ == "__main__":
    main()
