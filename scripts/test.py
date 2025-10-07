"""
Pinecone Embeddings Inspector Script
Tests and inspects all embeddings to find Section 3.1 (Subcontract Sum)
"""

import os
import sys
import django
import re

# Setup Django environment
# Adjust this path to your project's settings module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AI_doc_process.settings')  # Change this!
django.setup()

from django.conf import settings
from pinecone import Pinecone
from documents.services.pinecone_service import PineconeEmbedding


class PineconeInspector:
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self.index_name = getattr(settings, "PINECONE_INDEX_NAME", "ai-docs-index")
        
        # Initialize Pinecone
        api_key = getattr(settings, "PINECONE_API_KEY", None)
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY not configured")
        
        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(self.index_name)
        self.embedding_service = PineconeEmbedding(namespace=namespace)
    
    def get_index_stats(self):
        """Get overall index statistics"""
        stats = self.index.describe_index_stats()
        print("\n" + "="*80)
        print("INDEX STATISTICS")
        print("="*80)
        print(f"Index Name: {self.index_name}")
        print(f"Total Vectors: {stats.get('total_vector_count', 0)}")
        print("\nNamespaces:")
        for ns, ns_stats in stats.get('namespaces', {}).items():
            print(f"  - {ns}: {ns_stats.get('vector_count', 0)} vectors")
        print("="*80 + "\n")
        return stats
    
    def fetch_all_vectors(self, document_id: str = None, batch_size: int = 100):
        """
        Fetch all vectors from the namespace
        Since Pinecone doesn't support listing all IDs directly, we'll use query with dummy vector
        """
        print(f"\n🔍 Fetching vectors from namespace: '{self.namespace}'")
        
        # Get a sample vector to use its dimension
        stats = self.index.describe_index_stats()
        ns_stats = stats.get('namespaces', {}).get(self.namespace)
        
        if not ns_stats:
            print(f"❌ Namespace '{self.namespace}' not found!")
            return []
        
        vector_count = ns_stats.get('vector_count', 0)
        print(f"📊 Total vectors in namespace: {vector_count}")
        
        # Use similarity search with a dummy query to get all vectors
        # This is a workaround since Pinecone doesn't have a direct "list all" API
        try:
            # Create a zero vector for dimension-agnostic querying
            dimension = self.embedding_service.dimension
            dummy_vector = [0.0] * dimension
            
            filter_dict = None
            if document_id:
                filter_dict = {"document_id": {"$eq": document_id}}
            
            results = self.index.query(
                namespace=self.namespace,
                vector=dummy_vector,
                top_k=min(10000, vector_count),  # Pinecone max is 10000
                include_metadata=True,
                filter=filter_dict
            )
            
            matches = results.get('matches', [])
            print(f"✅ Retrieved {len(matches)} vectors")
            return matches
            
        except Exception as e:
            print(f"❌ Error fetching vectors: {e}")
            return []
    
    def search_for_section_3_1(self):
        """Specifically search for Section 3.1 content"""
        print("\n" + "="*80)
        print("SEARCHING FOR SECTION 3.1 (THE SUBCONTRACT SUM)")
        print("="*80)
        
        search_queries = [
            "3.1 The Contractor shall pay to the Subcontractor",
            "Subcontract sum £181,726",
            "contractor shall pay subcontractor VAT exclusive",
            "One Hundred and Eighty One Thousand",
            "£181,726.19",
            "THE SUBCONTRACT SUM",
        ]
        
        all_results = {}
        
        for query in search_queries:
            print(f"\n🔎 Query: '{query}'")
            results = self.embedding_service.similarity_search(query, top_k=5)
            matches = results.get('matches', []) if isinstance(results, dict) else getattr(results, 'matches', [])
            
            print(f"   Found {len(matches)} matches")
            
            for i, match in enumerate(matches[:3]):  # Show top 3
                metadata = match.get('metadata', {}) if isinstance(match, dict) else getattr(match, 'metadata', {})
                score = match.get('score', 0) if isinstance(match, dict) else getattr(match, 'score', 0)
                match_id = match.get('id', '') if isinstance(match, dict) else getattr(match, 'id', '')
                
                text = metadata.get('text', '')[:200]
                section = metadata.get('section_label', 'N/A')
                
                print(f"   [{i+1}] Score: {score:.4f} | Section: {section}")
                print(f"       ID: {match_id}")
                print(f"       Text: {text}...")
                
                if match_id not in all_results or all_results[match_id]['score'] < score:
                    all_results[match_id] = {
                        'score': score,
                        'metadata': metadata,
                        'query': query
                    }
        
        return all_results
    
    def analyze_all_chunks(self, document_id: str = None):
        """Analyze all chunks to find section 3.1"""
        print("\n" + "="*80)
        print("ANALYZING ALL CHUNKS FOR SECTION 3.1")
        print("="*80)
        
        vectors = self.fetch_all_vectors(document_id)
        
        if not vectors:
            print("❌ No vectors found!")
            return
        
        # Find chunks containing financial information
        financial_chunks = []
        section_3_chunks = []
        
        patterns = {
            'has_amount': r'£181,726',
            'has_section_3': r'3\.\d+\s+',
            'has_payment_clause': r'contractor shall pay',
            'has_subcontract_sum': r'subcontract sum',
            'has_section_header': r'3\.0\s+THE SUBCONTRACT SUM',
        }
        
        print(f"\n🔍 Analyzing {len(vectors)} chunks...\n")
        
        for vector in vectors:
            metadata = vector.get('metadata', {}) if isinstance(vector, dict) else getattr(vector, 'metadata', {})
            text = metadata.get('text', '')
            section_label = metadata.get('section_label', '')
            chunk_index = metadata.get('chunk_index', 'N/A')
            vector_id = vector.get('id', '') if isinstance(vector, dict) else getattr(vector, 'id', '')
            
            matches = {}
            for pattern_name, pattern in patterns.items():
                if re.search(pattern, text, re.IGNORECASE):
                    matches[pattern_name] = True
            
            if matches:
                financial_chunks.append({
                    'id': vector_id,
                    'chunk_index': chunk_index,
                    'section_label': section_label,
                    'text': text,
                    'matches': matches,
                    'metadata': metadata
                })
            
            # Check if it's section 3.x
            if re.search(r'3\.\d+', text) or '3.0' in section_label or '3.1' in section_label:
                section_3_chunks.append({
                    'id': vector_id,
                    'chunk_index': chunk_index,
                    'section_label': section_label,
                    'text': text[:500],
                    'metadata': metadata
                })
        
        # Display results
        print(f"📊 Found {len(financial_chunks)} chunks with financial information")
        print(f"📊 Found {len(section_3_chunks)} chunks related to Section 3.x\n")
        
        if financial_chunks:
            print("\n" + "-"*80)
            print("CHUNKS WITH FINANCIAL INFORMATION:")
            print("-"*80)
            for i, chunk in enumerate(financial_chunks, 1):
                print(f"\n[{i}] Chunk Index: {chunk['chunk_index']} | Section: {chunk['section_label']}")
                print(f"    Vector ID: {chunk['id']}")
                print(f"    Matches: {', '.join(chunk['matches'].keys())}")
                print(f"    Text Preview:\n    {chunk['text'][:300]}...")
                print("-"*80)
        
        if section_3_chunks:
            print("\n" + "-"*80)
            print("ALL SECTION 3.X CHUNKS:")
            print("-"*80)
            for i, chunk in enumerate(section_3_chunks, 1):
                print(f"\n[{i}] Chunk Index: {chunk['chunk_index']} | Section: {chunk['section_label']}")
                print(f"    Vector ID: {chunk['id']}")
                print(f"    Text Preview:\n    {chunk['text'][:400]}...")
                print("-"*80)
        
        return financial_chunks, section_3_chunks
    
    def check_section_3_1_exists(self):
        """
        Definitive check: Does section 3.1 with the payment amount exist in embeddings?
        """
        print("\n" + "="*80)
        print("DEFINITIVE CHECK: DOES SECTION 3.1 EXIST?")
        print("="*80)
        
        vectors = self.fetch_all_vectors()
        
        found_section_3_1 = False
        found_amount = False
        
        for vector in vectors:
            metadata = vector.get('metadata', {}) if isinstance(vector, dict) else getattr(vector, 'metadata', {})
            text = metadata.get('text', '')
            section_label = metadata.get('section_label', '')
            
            # Check for section 3.1 specifically
            if re.search(r'3\.1\s+The Contractor shall pay', text, re.IGNORECASE):
                found_section_3_1 = True
                print("\n✅ FOUND Section 3.1 clause!")
                print(f"   Section Label: {section_label}")
                print(f"   Vector ID: {vector.get('id', '') if isinstance(vector, dict) else getattr(vector, 'id', '')}")
                print(f"   Text:\n   {text[:600]}")
            
            # Check for the specific amount
            if '£181,726' in text or '181,726' in text:
                found_amount = True
                if not found_section_3_1:  # Only print if we haven't already
                    print("\n✅ FOUND the payment amount!")
                    print(f"   Section Label: {section_label}")
                    print(f"   Vector ID: {vector.get('id', '') if isinstance(vector, dict) else getattr(vector, 'id', '')}")
                    print(f"   Text:\n   {text[:600]}")
        
        print("\n" + "="*80)
        print("FINAL VERDICT:")
        print("="*80)
        if found_section_3_1 and found_amount:
            print("✅ Section 3.1 with payment amount EXISTS in embeddings")
        elif found_section_3_1:
            print("⚠️  Section 3.1 exists but payment amount not found in same chunk")
        elif found_amount:
            print("⚠️  Payment amount exists but not in Section 3.1 format")
        else:
            print("❌ Section 3.1 NOT FOUND in embeddings - Document needs re-indexing!")
        print("="*80 + "\n")
        
        return found_section_3_1, found_amount


def main():
    """Main execution function"""
    # from chat.models import ChatSession
    # data = ChatSession.objects.first()
    # print(data.namespace)

    print("\n" + "="*80)
    print("PINECONE EMBEDDINGS INSPECTOR")
    print("="*80)

    # Get namespace from user or use default
    namespace = "session_9e015a25_ea71_4f38_8bb4_67964c962e8c"

    # Optionally filter by document ID
    doc_id = "bd111511-577b-4cc8-ad38-ea751a63388f"

    inspector = PineconeInspector(namespace=namespace)

    # Run all checks
    print("\n1️⃣  Getting index statistics...")
    inspector.get_index_stats()

    print("\n2️⃣  Checking if Section 3.1 exists...")
    inspector.check_section_3_1_exists()

    print("\n3️⃣  Searching for Section 3.1 with semantic search...")
    inspector.search_for_section_3_1()

    print("\n4️⃣  Analyzing all chunks for financial content...")
    inspector.analyze_all_chunks(document_id=doc_id)

    print("\n✅ Inspection complete!")
    print("\n" + "="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Inspection cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error during inspection: {e}")
        import traceback
        traceback.print_exc()