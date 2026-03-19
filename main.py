import sys
from adapters import OpenAIAdapter

def main():
    """
    Main entry point for the Sovereign Synapse Ingestor.
    """
    # Simple CLI logic for Phase 1
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_export_json>")
        return

    input_file = sys.argv[1]
    
    print(f"🏛️ Initializing Sovereign Ingest for: {input_file}")
    
    # Initialize the adapter (Defaulting to OpenAI for Sprint 1)
    adapter = OpenAIAdapter(output_path="vault/synapses")
    
    try:
        adapter.parse(input_file)
        print("✅ Ingestion complete. Check /vault/synapses for your new history.")
    except Exception as e:
        print(f"❌ Critical Error during ingestion: {e}")

if __name__ == "__main__":
    main()
