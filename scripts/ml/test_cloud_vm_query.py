#!/usr/bin/env python3
"""
Test Cloud VM Query - Practical Use Case
=========================================

This script demonstrates a practical use case for the Cloud Agent embeddings:
- User queries: "I need a VM on AWS" or "Looking for cloud compute resources"
- System searches precomputed embeddings
- Returns relevant VM/resource recommendations with details

Usage:
    python scripts/test_cloud_vm_query.py
    python scripts/test_cloud_vm_query.py --query "I need a high performance VM on AWS"
"""

import os
import sys
import argparse
import pickle
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss


class CloudVMQueryAssistant:
    """Assistant for querying cloud VM resources using embeddings"""
    
    def __init__(self, index_dir: str = None):
        """Initialize the query assistant"""
        self.index_dir = Path(index_dir) if index_dir else PROJECT_ROOT / "data" / "faiss_indexes"
        self.model = None
        self.faiss_index = None
        self.id_to_content = {}
        self.id_to_metadata = {}
        self.content_type_map = {}
        self.stats = {}
    
    def load_model_and_index(self):
        """Load the SentenceTransformer model and FAISS index"""
        print("🔄 Loading embeddings model and index...")
        
        # Load model
        model_name = "all-MiniLM-L6-v2"
        print(f"   Loading model: {model_name}")
        self.model = SentenceTransformer(model_name)
        
        # Load FAISS index
        index_path = self.index_dir / "cloud_embeddings.faiss"
        metadata_path = self.index_dir / "cloud_embeddings_metadata.pkl"
        
        if not index_path.exists():
            print(f"❌ Index not found at: {index_path}")
            print("   Please run: python scripts/precompute_cloud_embeddings.py")
            return False
        
        print(f"   Loading FAISS index: {index_path}")
        self.faiss_index = faiss.read_index(str(index_path))
        
        # Load metadata
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        
        self.id_to_content = metadata["id_to_content"]
        self.id_to_metadata = metadata["id_to_metadata"]
        self.content_type_map = metadata["content_type_map"]
        self.stats = metadata["stats"]
        
        print(f"✅ Loaded {self.faiss_index.ntotal} embeddings")
        print(f"   Data types available: {', '.join(self.stats['by_type'].keys())}")
        return True
    
    def search_resources(
        self,
        query: str,
        k: int = 5,
        content_type: str = "cloud_resources"
    ) -> List[Dict[str, Any]]:
        """Search for cloud resources matching the query"""
        # Generate query embedding
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        # Search in FAISS (get more results to filter)
        distances, indices = self.faiss_index.search(query_embedding.astype('float32'), k * 3)
        
        # Filter and format results
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < 0:
                continue
            
            # Filter by content type
            if self.content_type_map.get(idx) != content_type:
                continue
            
            result = {
                "similarity": float(distance),
                "content": self.id_to_content.get(idx, ""),
                "metadata": self.id_to_metadata.get(idx, {}),
                "content_type": self.content_type_map.get(idx, "unknown")
            }
            results.append(result)
            
            if len(results) >= k:
                break
        
        return results
    
    def format_vm_recommendation(self, result: Dict[str, Any], rank: int) -> str:
        """Format a VM resource recommendation for display"""
        metadata = result["metadata"]
        similarity = result["similarity"]
        
        output = []
        output.append(f"\n{'='*70}")
        output.append(f"🖥️  Recommendation #{rank} (Relevance: {similarity:.1%})")
        output.append(f"{'='*70}")
        
        # Resource details
        output.append(f"Resource ID:    {metadata.get('resource_id', 'N/A')}")
        output.append(f"Resource Type:  {metadata.get('resource_type', 'N/A')}")
        output.append(f"Service:        {metadata.get('service', 'N/A')}")
        output.append(f"Region:         {metadata.get('region', 'N/A')}")
        output.append(f"Status:         {metadata.get('status', 'N/A')}")
        output.append(f"Monthly Cost:   ${metadata.get('cost_monthly', 0):.2f}")
        output.append(f"Tags:           {metadata.get('tags', 'N/A')}")
        
        # Full description
        output.append(f"\n📋 Description:")
        output.append(f"   {result['content']}")
        
        return "\n".join(output)
    
    def process_query(self, user_query: str):
        """Process a user query and return recommendations"""
        print("\n" + "="*70)
        print("🔍 Cloud VM Query Assistant")
        print("="*70)
        print(f"\n💬 Your Query: \"{user_query}\"")
        print("\n🔄 Searching for matching cloud resources...")
        
        # Search for resources
        results = self.search_resources(user_query, k=5)
        
        if not results:
            print("\n❌ No matching resources found.")
            print("   Try a different query or check if data is loaded.")
            return
        
        print(f"\n✅ Found {len(results)} matching resources:")
        
        # Display recommendations
        for i, result in enumerate(results, 1):
            print(self.format_vm_recommendation(result, i))
        
        # Summary and recommendations
        print("\n" + "="*70)
        print("💡 Summary & Recommendations")
        print("="*70)
        
        # Analyze results
        regions = set()
        services = set()
        total_cost = 0
        statuses = []
        
        for result in results:
            meta = result["metadata"]
            regions.add(meta.get("region", "unknown"))
            services.add(meta.get("service", "unknown"))
            total_cost += meta.get("cost_monthly", 0)
            statuses.append(meta.get("status", "unknown"))
        
        print(f"\n📊 Analysis:")
        print(f"   • Available Regions: {', '.join(regions)}")
        print(f"   • Services: {', '.join(services)}")
        print(f"   • Average Monthly Cost: ${total_cost/len(results):.2f}")
        print(f"   • Active Resources: {statuses.count('running')}/{len(results)}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        # Find cheapest option
        cheapest = min(results, key=lambda x: x["metadata"].get("cost_monthly", float('inf')))
        print(f"   • Lowest Cost Option: {cheapest['metadata'].get('resource_id')} "
              f"(${cheapest['metadata'].get('cost_monthly', 0):.2f}/month)")
        
        # Find most relevant
        most_relevant = results[0]
        print(f"   • Most Relevant: {most_relevant['metadata'].get('resource_id')} "
              f"({most_relevant['similarity']:.1%} match)")
        
        # Regional recommendations
        if len(regions) > 1:
            print(f"   • Consider region based on your location/latency requirements")
        
        print("\n" + "="*70)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="Test cloud VM query with embeddings"
    )
    parser.add_argument(
        "--query",
        type=str,
        default="I need a VM on AWS",
        help="Query string for VM search"
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default=None,
        help="Directory containing FAISS index"
    )
    
    args = parser.parse_args()
    
    # Initialize assistant
    assistant = CloudVMQueryAssistant(index_dir=args.index_dir)
    
    # Load model and index
    if not assistant.load_model_and_index():
        print("\n❌ Failed to load model and index")
        print("   Run this first: python scripts/precompute_cloud_embeddings.py")
        return 1
    
    # Process the query
    assistant.process_query(args.query)
    
    # Additional example queries
    print("\n\n" + "="*70)
    print("🎯 Try These Example Queries")
    print("="*70)
    example_queries = [
        "I need a high performance compute instance",
        "Looking for cost-effective cloud storage",
        "Need a database server in us-east region",
        "Show me production-ready VMs",
        "Find GPU instances for machine learning"
    ]
    
    for query in example_queries:
        print(f"   python scripts/test_cloud_vm_query.py --query \"{query}\"")
    
    print("="*70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

