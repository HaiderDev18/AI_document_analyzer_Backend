from pinecone import Pinecone, ServerlessSpec
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize OpenAI client with error handling
openai_key = os.getenv("OPENAI_API_KEY")
try:
    if openai_key and not openai_key.startswith("placeholder"):
        client = OpenAI(api_key=openai_key)
    else:
        print("OpenAI key is not set")
        client = None
except Exception:
    print("OpenAI key is not set")
    client = None

# Initialize Pinecone with error handling
pinecone_key = os.getenv("PINECONE_API_KEY")
try:
    if pinecone_key and not pinecone_key.startswith("placeholder"):
        pc = Pinecone(api_key=pinecone_key)
    else:
        print("Pinecone key is not set")
        pc = None
except Exception:
    print("Pinecone key is not set")
    pc = None


class PineconeEmbedding:
    def __init__(self, index_name="ai-docs-index", namespace="new-chapters"):
        self.pinecone_key = os.getenv("PINECONE_API_KEY")
        self.index_name = index_name
        self.dimension = 3072
        self.doc_path = None
        self.namespace = namespace
        self.pc = Pinecone(api_key=self.pinecone_key)
        try:
            self.index = self.pc.Index(self.index_name) if self.index_name else None
        except Exception as e:
            self.index = self.create_serverless_index()
            print(f"Error initializing Pinecone index: {str(e)}")

        # self.mongodb_service = MongoDBService()

    def create_serverless_index(self):
        index = self.pc.create_index(
            name=self.index_name,
            dimension=self.dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        return index

    def list_namespaces(self) -> list:
        """
        List all existing namespaces in a Pinecone index
        Returns list of namespace names (strings)
        """
        try:
            index = self.pc.Index(self.index_name)
            # Get index statistics
            stats = index.describe_index_stats()

            # Extract namespaces from statistics
            namespaces = list(stats.get("namespaces", {}).keys())

            return namespaces

        except Exception as e:
            print(f"Error listing namespaces: {str(e)}")
            return []

    def namespace_exists(self, index, namespace: str) -> bool:
        """Check if a namespace exists in the Pinecone index"""
        stats = index.describe_index_stats()
        return namespace in stats["namespaces"]

    def get_vectors_namespace(self, namespace: str = None):
        """Get vectors from a namespace in Pinecone index"""
        try:
            if namespace:
                index = self.pc.Index(self.index_name)
                vectors = index.list(namespace=namespace)
                return vectors
            else:
                index = self.pc.Index(self.index_name)
                # vectors = index.list(namespace=self.namespace)
                all_ids = []
                vectors = None
                for ids in index.list(namespace=self.namespace):
                    all_ids.append(ids)

                    vectors = index.fetch(ids=ids, namespace=self.namespace)

                return vectors
        except Exception as e:
            print(f"Error getting vectors: {str(e)}")
            return []

    def delete_namespace_index(self, namespace: str = None):
        """Delete a namespace from Pinecone index"""
        try:
            if namespace:
                index = self.pc.Index(self.index_name)
                index.delete(delete_all=True, namespace=namespace)

            else:
                print(f"Deleting namespace '{self.namespace}'...")
                index = self.pc.Index(self.index_name)
                index.delete(delete_all=True, namespace=self.namespace)

        except Exception as e:
            print(f"Error deleting namespace: {str(e)}")
            print(f"Namespace '{self.namespace}' does not exist")

    def create_vector_embeddings(
        self,
        context: List[str],
        id: str = None,
        file_name: str = None,
        file_path: str = None,
        project_id: str = None,
        user=None,
    ) -> List[Dict]:
        """
        Generate embeddings with enhanced chunking and metadata.

        Args:
            context (List[str]): List of text content to process
            id (str, optional): Document ID
            file_name (str, optional): Original file name
            file_path (str, optional): Path to the source file
            user: User object for analytics tracking

        Returns:
            List[Dict]: List of vectors with embeddings and metadata
        """
        try:
            # Text splitting configuration
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=3000,
                chunk_overlap=300,
                length_function=len,
                separators=["\n\n", "\n", " "],
            )
            chunks = text_splitter.split_text(context)

            # Process each text in context
            embeddings = []

            # Process each chunk
            for chunk_idx, chunk_text in enumerate(chunks):
                # print(f"\n\nProcessing chunk: {chunk_idx} for document ID: {id}")

                result = client.embeddings.create(
                    input=chunk_text, model="text-embedding-3-large"
                )

                # Track embedding usage for analytics
                if user:
                    try:
                        from analytics.services import AnalyticsHelper

                        AnalyticsHelper.log_embedding_usage(
                            user=user,
                            openai_response=result,
                            text_length=len(chunk_text),
                        )
                    except Exception as analytics_error:
                        print(f"Analytics tracking error: {analytics_error}")

                # Create a unique ID for each chunk
                if id:
                    unique_chunk_id = f"{id}-chunk-{chunk_idx}"
                else:
                    unique_chunk_id = f"doc_unknown-chunk-{chunk_idx}"

                # print(f"Generated unique_chunk_id: {unique_chunk_id}")
                # print(f"Chunk text: {chunk_text}...") # Print only start of chunk
                # create a unique id for the document
                document_id = f"{id}-{file_name}"
                metadata = {
                    "document_id": document_id,
                    "file_name": file_name,
                    "file_path": file_path,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk_text),
                    "text": chunk_text,  # Storing the actual chunk text in metadata is crucial for RAG
                    "timestamp": datetime.now().isoformat(),
                    "embedding_model": "text-embedding-3-large",
                }

                vector = {
                    "id": unique_chunk_id,  # Use the unique ID for the vector
                    "values": result.data[0].embedding,
                    "metadata": metadata,
                }

                embeddings.append(vector)

            if not embeddings:
                print(f"No embeddings generated for document ID: {id}")
                return None

            return embeddings

        except Exception as e:
            print(f"Error creating vector embeddings: {str(e)}")
            return None

    def upsert_generated_vector_embeddings(self, vectors: List[Dict[str, Any]]):
        """
        Upsert vectors to Pinecone index.

        Args:
            vectors (List[Dict[str, Any]]): List of vectors with embeddings and metadata.
        """
        index = self.pc.Index(self.index_name)

        # Batch upsert to optimize performance
        if self.namespace:
            batch_size = 20
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                try:
                    index.upsert(vectors=batch, namespace=self.namespace)
                except Exception as e:
                    print(f"Error upserting batch: {str(e)}")
                    raise
        index = self.pc.Index(self.index_name)
        return index

    def similarity_search(self, query, top_k=7):
        """Search Pinecone index for similar vectors"""
        try:
            embedding = client.embeddings.create(
                input=[query], model="text-embedding-3-large"
            )

            results = self.pc.Index(self.index_name).query(
                namespace=self.namespace,
                vector=embedding.data[0].embedding,
                top_k=top_k,
                include_metadata=True,
            )
            if not os.path.exists("uploads"):
                os.makedirs("uploads")
            with open(f"uploads/query_similarity_results.txt", "w") as f:
                f.write(str(results))
            return results
        except Exception as e:
            print(f"Error in similarity search: {str(e)}")
            return None

    def generate_response(self, query, search_results):
        """Generate LLM response using context from search results"""
        if search_results["matches"]:
            context = "\n".join(
                [f"- {match.metadata['text']}" for match in search_results["matches"]]
            )

            user_prompt = f"""Answer the question based on the context below. 
            You are a helpful assistant of knowledge base. You will assist the user with their questions based on the context provided.
            If context is not provided, this question is not relevant to the context that is stored in the knowledge base.
            You need to answer the question based on the context provided. The answer should be in a good format and should be clear and not too concise.
            Context: {context}
            
            Question: {query}
            Answer: """

            response = client.chat.completions.create(
                model="o1-mini",  # Use the appropriate GPT model
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response
        else:
            context = "No relevant context found for the question. Please try to save document in embeddings"
            user_prompt = f"""Answer the question based on the context below. 
            You are a helpful assistant of knowledge base. You will assist the user with their questions based on the context provided.
            If context is not provided, this question is not relevant to the context that is stored in the knowledge base.
            You need to answer the question based on the context provided. The answer should be in a good format and should be clear and not too concise.
            Context: {context}
            
            Question: {query}
            Answer: """

            response = client.chat.completions.create(
                model="o1-mini",  # Use the appropriate GPT model
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response

    def main(
        self,
        delete_namespace=None,
        text=None,
        id=None,
        file_name=None,
        file_path=None,
        user=None,
    ):
        if not self.pc.has_index(self.index_name):
            self.index = self.create_serverless_index()
        else:
            self.pc.describe_index(self.index_name)
            # print("this is the index: ", self.pc.describe_index(self.index_name))
            self.index = self.pc.Index(self.index_name)
        if id is None:
            if file_name:
                id = file_name[:30]
            else:
                id = "doc_unknown"
        if delete_namespace:
            if self.namespace_exists(self.index_name, delete_namespace):
                self.delete_namespace_index(self.index_name, delete_namespace)
            else:
                print(f"Namespace '{delete_namespace}' does not exist")

        if text:
            print("Entered the text if statement")
            embeddings = self.create_vector_embeddings(
                text, id=id, file_name=file_name, file_path=file_path, user=user
            )
            if self.namespace:
                index = self.upsert_generated_vector_embeddings(embeddings)
            else:
                index = self.upsert_generated_vector_embeddings(embeddings)


class PineconeService:
    """
    Service class for Pinecone vector operations using the existing PineconeEmbedding class
    """

    def __init__(self, namespace: str = None):
        from django.conf import settings

        self.index_name = settings.PINECONE_INDEX_NAME
        self.namespace = namespace
        self.pinecone_embedding = PineconeEmbedding(
            index_name=self.index_name, namespace=self.namespace
        )

    def store_document_chunks(
        self, document_id: str, chunks_data: List[Dict], file_name: str, file_path: str
    ):
        """
        Store document chunks in Pinecone using the existing PineconeEmbedding class
        """
        try:
            # Prepare text for embedding
            text_content = "\n".join([chunk["text"] for chunk in chunks_data])

            # Use the existing create_vector_embeddings method
            embeddings = self.pinecone_embedding.create_vector_embeddings(
                context=text_content,
                id=document_id,
                file_name=file_name,
                file_path=file_path,
            )

            if embeddings:
                # Upsert the embeddings
                self.pinecone_embedding.upsert_generated_vector_embeddings(embeddings)
                return True
            return False

        except Exception as e:
            raise Exception(f"Error storing document chunks: {str(e)}")

    def search_similar_chunks(
        self, query_embedding: List[float], user_id: str = None, top_k: int = 4
    ):
        """
        Search for similar chunks using the existing similarity search
        """
        try:
            # Convert embedding to query text for the existing method
            # Note: This is a workaround since the existing method expects a query string
            # In a real implementation, you'd modify the existing method to accept embeddings directly

            # For now, we'll use the index directly
            index = self.pinecone_embedding.pc.Index(self.index_name)
            results = index.query(
                namespace=self.namespace,
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
            )

            return results.matches if results else []

        except Exception as e:
            raise Exception(f"Error searching similar chunks: {str(e)}")

    def delete_vectors_by_filter(self, filter_dict: Dict):
        """
        Delete vectors by filter
        """
        try:
            index = self.pinecone_embedding.pc.Index(self.index_name)
            index.delete(namespace=self.namespace, filter=filter_dict)
        except Exception as e:
            raise Exception(f"Error deleting vectors: {str(e)}")

    def delete_namespace(self):
        """
        Delete entire namespace
        """
        try:
            self.pinecone_embedding.delete_namespace_index(self.namespace)
        except Exception as e:
            raise Exception(f"Error deleting namespace: {str(e)}")

    def create_index_if_not_exists(self):
        """
        Create index if it doesn't exist
        """
        try:
            if not self.pinecone_embedding.pc.has_index(self.index_name):
                self.pinecone_embedding.create_serverless_index()
        except Exception as e:
            raise Exception(f"Error creating index: {str(e)}")
