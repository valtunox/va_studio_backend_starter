#!/usr/bin/env python3
"""
Precompute Cloud Embeddings with FAISS Index
=============================================

This script precomputes embeddings for cloud operations data and stores them in a FAISS index.
It processes:
- Cloud logs (error patterns, anomalies)
- Cloud resources (infrastructure configurations)
- Cloud metrics (performance data)
- Cloud incidents (historical issues)
- Cloud knowledge base (best practices)

Architecture Context:
- Only the Cloud Agent uses embeddings (see CLOUD_MODEL_AGENT_ARCHITECTURE.md)
- Uses SentenceTransformer (all-MiniLM-L6-v2) for embeddings
- Uses FAISS IndexFlatIP for similarity search
- Saves index to disk for fast loading

Usage:
    python scripts/precompute_cloud_embeddings.py
    python scripts/precompute_cloud_embeddings.py --test-only
    python scripts/precompute_cloud_embeddings.py --index-path custom_path.faiss
"""

import os
import sys
import json
import argparse
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Third-party imports
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudEmbeddingsPrecompute:
    """Precompute and manage cloud embeddings with FAISS index"""
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        data_dir: str = None,
        index_dir: str = None,
        dimension: int = 384
    ):
        """
        Initialize the embeddings precompute system
        
        Args:
            model_name: SentenceTransformer model name
            data_dir: Directory containing cloud data CSV files
            index_dir: Directory to save FAISS index and metadata
            dimension: Embedding dimension (384 for all-MiniLM-L6-v2)
        """
        self.model_name = model_name
        self.dimension = dimension
        
        # Setup directories
        self.data_dir = Path(data_dir) if data_dir else PROJECT_ROOT / "app" / "data"
        self.index_dir = Path(index_dir) if index_dir else PROJECT_ROOT / "data" / "faiss_indexes"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.model = None
        self.faiss_index = None
        self.id_to_metadata = {}  # Maps FAISS index ID to metadata
        self.id_to_content = {}   # Maps FAISS index ID to original content
        self.content_type_map = {}  # Maps FAISS index ID to content type
        
        # Statistics
        self.stats = {
            "total_embeddings": 0,
            "by_type": {},
            "processing_time": 0,
            "model_name": model_name,
            "dimension": dimension,
            "timestamp": None
        }
    
    def initialize_model(self):
        """Initialize the SentenceTransformer model"""
        logger.info(f"Loading SentenceTransformer model: {self.model_name}")
        try:
            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"✅ Model loaded successfully (dimension: {self.dimension})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            return False
    
    def initialize_faiss_index(self):
        """Initialize FAISS index for similarity search"""
        logger.info("Initializing FAISS index...")
        try:
            # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
            self.faiss_index = faiss.IndexFlatIP(self.dimension)
            logger.info(f"✅ FAISS index initialized (dimension: {self.dimension})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize FAISS index: {e}")
            return False
    
    def process_cloud_logs(self) -> Tuple[List[str], List[Dict]]:
        """Process cloud logs and extract text + metadata"""
        logger.info("Processing cloud_logs.csv...")
        
        try:
            logs_df = pd.read_csv(self.data_dir / "cloud_logs.csv")
            
            texts = []
            metadata_list = []
            
            for _, row in logs_df.iterrows():
                # Create searchable text representation
                text = f"{row['log_level']} {row['message']} service:{row['service']} region:{row['region']}"
                texts.append(text)
                
                # Store metadata
                metadata = {
                    "content_type": "cloud_logs",
                    "instance_id": row['instance_id'],
                    "log_level": row['log_level'],
                    "service": row['service'],
                    "region": row['region'],
                    "timestamp": row['timestamp'],
                    "error_code": row['error_code']
                }
                metadata_list.append(metadata)
            
            logger.info(f"✅ Processed {len(texts)} cloud logs")
            return texts, metadata_list
            
        except FileNotFoundError:
            logger.warning("⚠️  cloud_logs.csv not found, skipping")
            return [], []
        except Exception as e:
            logger.error(f"❌ Error processing cloud logs: {e}")
            return [], []
    
    def process_cloud_resources(self) -> Tuple[List[str], List[Dict]]:
        """Process cloud resources and extract text + metadata"""
        logger.info("Processing cloud_resources.csv...")
        
        try:
            resources_df = pd.read_csv(self.data_dir / "cloud_resources.csv")
            
            texts = []
            metadata_list = []
            
            for _, row in resources_df.iterrows():
                # Create searchable text representation
                text = (
                    f"{row['resource_type']} {row['service']} in {row['region']} "
                    f"status:{row['status']} cost:${row['cost_monthly']} tags:{row['tags']}"
                )
                texts.append(text)
                
                # Store metadata
                metadata = {
                    "content_type": "cloud_resources",
                    "resource_id": row['resource_id'],
                    "resource_type": row['resource_type'],
                    "service": row['service'],
                    "region": row['region'],
                    "status": row['status'],
                    "cost_monthly": float(row['cost_monthly']),
                    "tags": row['tags']
                }
                metadata_list.append(metadata)
            
            logger.info(f"✅ Processed {len(texts)} cloud resources")
            return texts, metadata_list
            
        except FileNotFoundError:
            logger.warning("⚠️  cloud_resources.csv not found, skipping")
            return [], []
        except Exception as e:
            logger.error(f"❌ Error processing cloud resources: {e}")
            return [], []
    
    def process_cloud_metrics(self) -> Tuple[List[str], List[Dict]]:
        """Process cloud metrics and extract text + metadata"""
        logger.info("Processing cloud_metrics.csv...")
        
        try:
            metrics_df = pd.read_csv(self.data_dir / "cloud_metrics.csv")
            
            texts = []
            metadata_list = []
            
            for _, row in metrics_df.iterrows():
                # Create searchable text representation
                text = (
                    f"{row['metric_name']} for {row['resource_id']} in {row['region']}: "
                    f"{row['value']} {row['unit']} alert:{row['alert_status']}"
                )
                texts.append(text)
                
                # Store metadata
                metadata = {
                    "content_type": "cloud_metrics",
                    "metric_name": row['metric_name'],
                    "resource_id": row['resource_id'],
                    "service": row['service'],
                    "region": row['region'],
                    "value": float(row['value']),
                    "unit": row['unit'],
                    "alert_status": row['alert_status']
                }
                metadata_list.append(metadata)
            
            logger.info(f"✅ Processed {len(texts)} cloud metrics")
            return texts, metadata_list
            
        except FileNotFoundError:
            logger.warning("⚠️  cloud_metrics.csv not found, skipping")
            return [], []
        except Exception as e:
            logger.error(f"❌ Error processing cloud metrics: {e}")
            return [], []
    
    def process_cloud_incidents(self) -> Tuple[List[str], List[Dict]]:
        """Process cloud incidents and extract text + metadata"""
        logger.info("Processing cloud_incidents.csv...")
        
        try:
            incidents_df = pd.read_csv(self.data_dir / "cloud_incidents.csv")
            
            texts = []
            metadata_list = []
            
            for _, row in incidents_df.iterrows():
                # Create searchable text representation
                text = f"{row['severity']} {row['title']}: {row['description']}"
                texts.append(text)
                
                # Store metadata
                metadata = {
                    "content_type": "cloud_incidents",
                    "incident_id": row['incident_id'],
                    "severity": row['severity'],
                    "title": row['title'],
                    "service": row['service'],
                    "region": row['region'],
                    "status": row['status'],
                    "timestamp": row['timestamp']
                }
                metadata_list.append(metadata)
            
            logger.info(f"✅ Processed {len(texts)} cloud incidents")
            return texts, metadata_list
            
        except FileNotFoundError:
            logger.warning("⚠️  cloud_incidents.csv not found, skipping")
            return [], []
        except Exception as e:
            logger.error(f"❌ Error processing cloud incidents: {e}")
            return [], []
    
    def process_cloud_knowledge(self) -> Tuple[List[str], List[Dict]]:
        """Process cloud knowledge base and extract text + metadata"""
        logger.info("Processing cloud_knowledge.json...")
        
        try:
            with open(self.data_dir / "cloud_knowledge.json", 'r') as f:
                knowledge_items = json.load(f)
            
            texts = []
            metadata_list = []
            
            for idx, item in enumerate(knowledge_items):
                # Create searchable text representation
                text = f"{item['title']}: {item['content']}"
                texts.append(text)
                
                # Store metadata
                metadata = {
                    "content_type": "cloud_knowledge",
                    "knowledge_id": f"knowledge_{idx}",
                    "title": item['title']
                }
                metadata_list.append(metadata)
            
            logger.info(f"✅ Processed {len(texts)} knowledge base items")
            return texts, metadata_list
            
        except FileNotFoundError:
            logger.warning("⚠️  cloud_knowledge.json not found, skipping")
            return [], []
        except Exception as e:
            logger.error(f"❌ Error processing cloud knowledge: {e}")
            return [], []
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for texts in batches"""
        if not texts:
            return np.array([])
        
        logger.info(f"Generating embeddings for {len(texts)} texts...")
        
        try:
            # Generate embeddings in batches
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            
            # Normalize embeddings for cosine similarity (IndexFlatIP requires this)
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            
            logger.info(f"✅ Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Error generating embeddings: {e}")
            return np.array([])
    
    def add_to_faiss_index(
        self,
        embeddings: np.ndarray,
        texts: List[str],
        metadata_list: List[Dict]
    ):
        """Add embeddings to FAISS index and store metadata"""
        if len(embeddings) == 0:
            return
        
        # Get starting index ID
        start_idx = self.faiss_index.ntotal
        
        # Add to FAISS index
        self.faiss_index.add(embeddings.astype('float32'))
        
        # Store metadata and content
        for i, (text, metadata) in enumerate(zip(texts, metadata_list)):
            idx = start_idx + i
            self.id_to_content[idx] = text
            self.id_to_metadata[idx] = metadata
            
            content_type = metadata.get("content_type", "unknown")
            self.content_type_map[idx] = content_type
            
            # Update statistics
            self.stats["by_type"][content_type] = self.stats["by_type"].get(content_type, 0) + 1
        
        self.stats["total_embeddings"] = self.faiss_index.ntotal
        logger.info(f"✅ Added {len(embeddings)} vectors to FAISS index (total: {self.faiss_index.ntotal})")
    
    def precompute_all(self):
        """Precompute embeddings for all cloud data"""
        logger.info("=" * 70)
        logger.info("🚀 Starting Cloud Embeddings Precomputation")
        logger.info("=" * 70)
        
        start_time = datetime.now()
        
        # Initialize model and index
        if not self.initialize_model():
            return False
        
        if not self.initialize_faiss_index():
            return False
        
        # Process each data source
        data_sources = [
            self.process_cloud_logs,
            self.process_cloud_resources,
            self.process_cloud_metrics,
            self.process_cloud_incidents,
            self.process_cloud_knowledge
        ]
        
        for process_func in data_sources:
            texts, metadata_list = process_func()
            
            if texts:
                embeddings = self.generate_embeddings(texts)
                if len(embeddings) > 0:
                    self.add_to_faiss_index(embeddings, texts, metadata_list)
        
        # Calculate processing time
        end_time = datetime.now()
        self.stats["processing_time"] = (end_time - start_time).total_seconds()
        self.stats["timestamp"] = end_time.isoformat()
        
        # Display summary
        self.display_summary()
        
        return True
    
    def display_summary(self):
        """Display summary statistics"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 Embeddings Summary")
        logger.info("=" * 70)
        logger.info(f"Total embeddings: {self.stats['total_embeddings']}")
        logger.info(f"Embedding dimension: {self.stats['dimension']}")
        logger.info(f"Model: {self.stats['model_name']}")
        logger.info(f"Processing time: {self.stats['processing_time']:.2f} seconds")
        logger.info(f"\nEmbeddings by type:")
        for content_type, count in self.stats["by_type"].items():
            logger.info(f"  • {content_type}: {count}")
        logger.info("=" * 70)
    
    def save_index(self, index_path: str = None, metadata_path: str = None):
        """Save FAISS index and metadata to disk"""
        if index_path is None:
            index_path = self.index_dir / "cloud_embeddings.faiss"
        if metadata_path is None:
            metadata_path = self.index_dir / "cloud_embeddings_metadata.pkl"
        
        logger.info(f"\n💾 Saving FAISS index to: {index_path}")
        
        try:
            # Save FAISS index
            faiss.write_index(self.faiss_index, str(index_path))
            
            # Save metadata
            metadata = {
                "id_to_content": self.id_to_content,
                "id_to_metadata": self.id_to_metadata,
                "content_type_map": self.content_type_map,
                "stats": self.stats
            }
            
            with open(metadata_path, 'wb') as f:
                pickle.dump(metadata, f)
            
            logger.info(f"✅ Index saved: {index_path}")
            logger.info(f"✅ Metadata saved: {metadata_path}")
            
            # Save stats as JSON for easy reading
            stats_path = self.index_dir / "cloud_embeddings_stats.json"
            with open(stats_path, 'w') as f:
                json.dump(self.stats, f, indent=2)
            logger.info(f"✅ Stats saved: {stats_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving index: {e}")
            return False
    
    def load_index(self, index_path: str = None, metadata_path: str = None):
        """Load FAISS index and metadata from disk"""
        if index_path is None:
            index_path = self.index_dir / "cloud_embeddings.faiss"
        if metadata_path is None:
            metadata_path = self.index_dir / "cloud_embeddings_metadata.pkl"
        
        logger.info(f"📂 Loading FAISS index from: {index_path}")
        
        try:
            # Load FAISS index
            self.faiss_index = faiss.read_index(str(index_path))
            
            # Load metadata
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            
            self.id_to_content = metadata["id_to_content"]
            self.id_to_metadata = metadata["id_to_metadata"]
            self.content_type_map = metadata["content_type_map"]
            self.stats = metadata["stats"]
            
            logger.info(f"✅ Loaded index with {self.faiss_index.ntotal} vectors")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading index: {e}")
            return False
    
    def similarity_search(
        self,
        query_text: str,
        k: int = 5,
        content_type_filter: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar items in the FAISS index
        
        Args:
            query_text: Text to search for
            k: Number of results to return
            content_type_filter: Filter by content type (e.g., "cloud_logs")
        
        Returns:
            List of results with content, metadata, and similarity scores
        """
        if self.faiss_index is None or self.faiss_index.ntotal == 0:
            logger.warning("Index is empty or not initialized")
            return []
        
        # Generate query embedding
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        # Search in FAISS
        distances, indices = self.faiss_index.search(query_embedding.astype('float32'), k)
        
        # Format results
        results = []
        for i, (idx, distance) in enumerate(zip(indices[0], distances[0])):
            if idx < 0:  # Invalid index
                continue
            
            # Apply content type filter if specified
            if content_type_filter and self.content_type_map.get(idx) != content_type_filter:
                continue
            
            result = {
                "rank": i + 1,
                "similarity": float(distance),  # For IndexFlatIP, this is cosine similarity
                "content": self.id_to_content.get(idx, ""),
                "metadata": self.id_to_metadata.get(idx, {}),
                "content_type": self.content_type_map.get(idx, "unknown")
            }
            results.append(result)
        
        return results


def run_tests(embeddings_system: CloudEmbeddingsPrecompute):
    """Run comprehensive tests on the embeddings system"""
    logger.info("\n" + "=" * 70)
    logger.info("🧪 Running Embeddings Tests")
    logger.info("=" * 70)
    
    test_results = {
        "passed": 0,
        "failed": 0,
        "tests": []
    }
    
    # Test 1: Basic similarity search
    logger.info("\n[Test 1] Basic Similarity Search")
    try:
        results = embeddings_system.similarity_search("database connection error", k=3)
        assert len(results) > 0, "No results found"
        assert all("similarity" in r for r in results), "Missing similarity scores"
        logger.info(f"✅ Found {len(results)} results")
        for i, result in enumerate(results[:3], 1):
            logger.info(f"   {i}. {result['content'][:60]}... (score: {result['similarity']:.3f})")
        test_results["passed"] += 1
        test_results["tests"].append({"name": "Basic Search", "status": "PASSED"})
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        test_results["failed"] += 1
        test_results["tests"].append({"name": "Basic Search", "status": "FAILED", "error": str(e)})
    
    # Test 2: Content type filtering
    logger.info("\n[Test 2] Content Type Filtering")
    try:
        results = embeddings_system.similarity_search(
            "high cost resources",
            k=3,
            content_type_filter="cloud_resources"
        )
        assert len(results) > 0, "No results found"
        assert all(r["content_type"] == "cloud_resources" for r in results), "Filter not working"
        logger.info(f"✅ Found {len(results)} cloud_resources results")
        for i, result in enumerate(results[:3], 1):
            logger.info(f"   {i}. {result['content'][:60]}... (score: {result['similarity']:.3f})")
        test_results["passed"] += 1
        test_results["tests"].append({"name": "Content Type Filter", "status": "PASSED"})
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        test_results["failed"] += 1
        test_results["tests"].append({"name": "Content Type Filter", "status": "FAILED", "error": str(e)})
    
    # Test 3: Find critical incidents
    logger.info("\n[Test 3] Find Critical Incidents")
    try:
        results = embeddings_system.similarity_search(
            "critical database failure",
            k=3,
            content_type_filter="cloud_incidents"
        )
        logger.info(f"✅ Found {len(results)} incident results")
        for i, result in enumerate(results[:3], 1):
            logger.info(f"   {i}. {result['content'][:60]}... (score: {result['similarity']:.3f})")
        test_results["passed"] += 1
        test_results["tests"].append({"name": "Critical Incidents", "status": "PASSED"})
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        test_results["failed"] += 1
        test_results["tests"].append({"name": "Critical Incidents", "status": "FAILED", "error": str(e)})
    
    # Test 4: Cloud knowledge search
    logger.info("\n[Test 4] Cloud Knowledge Search")
    try:
        results = embeddings_system.similarity_search(
            "best practices for network security",
            k=3,
            content_type_filter="cloud_knowledge"
        )
        logger.info(f"✅ Found {len(results)} knowledge base results")
        for i, result in enumerate(results[:3], 1):
            logger.info(f"   {i}. {result['content'][:60]}... (score: {result['similarity']:.3f})")
        test_results["passed"] += 1
        test_results["tests"].append({"name": "Knowledge Search", "status": "PASSED"})
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        test_results["failed"] += 1
        test_results["tests"].append({"name": "Knowledge Search", "status": "FAILED", "error": str(e)})
    
    # Test 5: Performance metrics search
    logger.info("\n[Test 5] Performance Metrics Search")
    try:
        results = embeddings_system.similarity_search(
            "high cpu usage alert",
            k=3,
            content_type_filter="cloud_metrics"
        )
        logger.info(f"✅ Found {len(results)} metrics results")
        for i, result in enumerate(results[:3], 1):
            logger.info(f"   {i}. {result['content'][:60]}... (score: {result['similarity']:.3f})")
        test_results["passed"] += 1
        test_results["tests"].append({"name": "Metrics Search", "status": "PASSED"})
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        test_results["failed"] += 1
        test_results["tests"].append({"name": "Metrics Search", "status": "FAILED", "error": str(e)})
    
    # Test 6: Save and load index
    logger.info("\n[Test 6] Save and Load Index")
    try:
        # Save
        test_index_path = embeddings_system.index_dir / "test_index.faiss"
        test_metadata_path = embeddings_system.index_dir / "test_metadata.pkl"
        
        embeddings_system.save_index(test_index_path, test_metadata_path)
        
        # Load into new instance
        test_system = CloudEmbeddingsPrecompute()
        test_system.initialize_model()
        test_system.load_index(test_index_path, test_metadata_path)
        
        # Verify
        assert test_system.faiss_index.ntotal == embeddings_system.faiss_index.ntotal, "Index size mismatch"
        
        # Clean up test files
        test_index_path.unlink()
        test_metadata_path.unlink()
        
        logger.info(f"✅ Successfully saved and loaded index")
        test_results["passed"] += 1
        test_results["tests"].append({"name": "Save/Load Index", "status": "PASSED"})
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        test_results["failed"] += 1
        test_results["tests"].append({"name": "Save/Load Index", "status": "FAILED", "error": str(e)})
    
    # Display test summary
    logger.info("\n" + "=" * 70)
    logger.info("📋 Test Results Summary")
    logger.info("=" * 70)
    logger.info(f"Total Tests: {test_results['passed'] + test_results['failed']}")
    logger.info(f"✅ Passed: {test_results['passed']}")
    logger.info(f"❌ Failed: {test_results['failed']}")
    logger.info("")
    for test in test_results["tests"]:
        status_icon = "✅" if test["status"] == "PASSED" else "❌"
        logger.info(f"{status_icon} {test['name']}: {test['status']}")
        if "error" in test:
            logger.info(f"   Error: {test['error']}")
    logger.info("=" * 70)
    
    return test_results["failed"] == 0


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="Precompute cloud embeddings with FAISS index"
    )
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Only run tests on existing index (skip precomputation)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Directory containing cloud data CSV files"
    )
    parser.add_argument(
        "--index-path",
        type=str,
        default=None,
        help="Path to save/load FAISS index"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="all-MiniLM-L6-v2",
        help="SentenceTransformer model name"
    )
    
    args = parser.parse_args()
    
    # Initialize embeddings system
    embeddings_system = CloudEmbeddingsPrecompute(
        model_name=args.model_name,
        data_dir=args.data_dir
    )
    
    if args.test_only:
        # Load existing index and run tests
        logger.info("Running in test-only mode...")
        embeddings_system.initialize_model()
        
        if args.index_path:
            metadata_path = str(Path(args.index_path).with_suffix('.pkl'))
            success = embeddings_system.load_index(args.index_path, metadata_path)
        else:
            success = embeddings_system.load_index()
        
        if not success:
            logger.error("Failed to load index. Run without --test-only to create it first.")
            return 1
        
        # Run tests
        all_passed = run_tests(embeddings_system)
        return 0 if all_passed else 1
    
    else:
        # Precompute embeddings
        success = embeddings_system.precompute_all()
        
        if not success:
            logger.error("Failed to precompute embeddings")
            return 1
        
        # Save index
        if args.index_path:
            metadata_path = str(Path(args.index_path).with_suffix('.pkl'))
            embeddings_system.save_index(args.index_path, metadata_path)
        else:
            embeddings_system.save_index()
        
        # Run tests
        logger.info("\n🔄 Running validation tests...")
        all_passed = run_tests(embeddings_system)
        
        if all_passed:
            logger.info("\n" + "=" * 70)
            logger.info("✅ Cloud embeddings precomputation completed successfully!")
            logger.info("=" * 70)
            return 0
        else:
            logger.warning("\n⚠️  Some tests failed. Please review the output above.")
            return 1


if __name__ == "__main__":
    sys.exit(main())

